import json
import os
import sys
import argparse
import folium
import pandas as pd
import requests
import random
import geoip2.database
import socket
import branca.colormap as cm
import pygeohash

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Generate Indexer Maps")
parser.add_argument("--url", help="URL of the leaderboard JSON data")
parser.add_argument("--output-dir", help="Output directory for the HTML files")
args = parser.parse_args()

# Set URL and output directory from command-line arguments or environment variables
url = args.url or os.environ.get("URL", "https://thegraph.com/_next/data/1S8gjhHRAo46eQdAneE-H/migration-incentive-program/leaderboard.json")
output_dir = args.output_dir or os.environ.get("OUTPUT_DIR", "output")

# Make request to url and get JSON response
response = requests.get(url)
data = json.loads(response.text)

# Extract data
indexer_data = data['pageProps']['participants']

# Create a geoip object
reader = geoip2.database.Reader('GeoLite2-City.mmdb')
asnReader = geoip2.database.Reader('GeoLite2-ASN.mmdb')

# GraphQL endpoints
endpoints = {
    "goerli": "https://gateway.testnet.thegraph.com/network",
    "mainnet": "https://gateway.thegraph.com/network"
}

# GraphQL query
query = """
query MyQuery($first: Int!, $after: String) {
  indexers(first: $first, where: { id_gt: $after }) {
    id
    geoHash
    url
  }
}
"""


map_links = []

# Loop through the networks
for network, endpoint in endpoints.items():
    print(f"Processing {network} network...")
    after = "0"

    # Initialize the variables for pagination
    first = 100
    indexers = []

    # Execute the GraphQL query with pagination
    while True:
        variables = {"first": first, "after": after}
        response = requests.post(endpoint, json={"query": query, "variables": variables})
        result = response.json()["data"]["indexers"]
        if len(result) == 0:
            break
        indexers.extend(result)
        after = result[-1]["id"]
        print(f"Processed {len(indexers)} indexers")
    # Convert the indexer data into a pandas DataFrame
    indexer_df = pd.DataFrame(indexers)

    ip_cache = {}

    # Network-specific score types
    score_types = {
        "goerli": ["celoPhase1Score", "gnosisPhase1Score", "gnosisExtraScore", "arbitrumPhase1Score", "avalanchePhase1Score"],
        "mainnet": ["gnosisPhase2Score"]
    }

    for score_type in score_types[network]:

        print(f"Processing score type: {score_type}...")

        # Create indexer_score_map based on the network
        if network == "goerli":
            indexer_score_map = {
                indexer['indexerGoerliAddress'].lower(): indexer[score_type]
                for indexer in indexer_data
                if indexer['indexerGoerliAddress'] is not None
            }
        elif network == "mainnet":
            indexer_score_map = {
                indexer['indexerMainnetAddress'].lower(): indexer[score_type]
                for indexer in indexer_data
                if indexer['indexerMainnetAddress'] is not None
            }

        # Create a copy of the original indexer DataFrame
        df = indexer_df.copy()

        # Map indexer address to indexer score based on the network
        address_column = "indexerGoerliAddress" if network == "goerli" else "indexerMainnetAddress"
        df['score'] = df['id'].map(indexer_score_map)

        # Remove rows with empty score
        df = df[df["score"].notna()]

        # Replace empty url with http://example.com
        df["url"] = df["url"].fillna("http://example.com")
        df.reset_index(drop=True)

        # Remove rows with invalid url
        df = df[df["url"].str.contains("http")]

        # Convert URL list to host list
        df["host"] = [row["url"].split("://")[1].split("/")[0].split(":")[0] for i, row in df.iterrows()]

        # Convert host to IP and cache the results
        for i, row in df.iterrows():
            host = row["host"]
            try:
                if host not in ip_cache:
                    ip = socket.gethostbyname(host)
                    city = reader.city(ip)
                    lat = city.location.latitude
                    long = city.location.longitude
                    asn_org = asnReader.asn(ip).autonomous_system_organization
                    ip_cache[host] = (ip, city.city.name, long, lat, asn_org)
                else:
                    ip, city_name, long, lat, asn_org = ip_cache[host]

                df.loc[i, "provider"] = asn_org
                if lat is None:
                    lat = 0
                if long is None:
                    long = 0
                df.loc[i, "longitude"] = float(long)
                df.loc[i, "latitude"] = float(lat)
            except socket.gaierror:
                df.loc[i, "ip"] = "127.0.0.1"
                df.loc[i, "longitude"] = 0
                df.loc[i, "latitude"] = 0
            except geoip2.errors.AddressNotFoundError:
                df.loc[i, "longitude"] = 0
                df.loc[i, "latitude"] = 0

        # Replace latitude and longitude with geohash
        for i, row in df.iterrows():
            try:
                coord = pygeohash.decode(row["geoHash"])
                df.loc[i, "selfreport_latitude"] = pygeohash.decode(row["geoHash"])[0]
                df.loc[i, "selfreport_longitude"] = pygeohash.decode(row["geoHash"])[1]
            except TypeError:
                df.loc[i, "selfreport_latitude"] = 0
                df.loc[i, "selfreport_longitude"] = 0

        # Remove rows with provider CLOUDFLARENET
        df = df[df["provider"] != "CLOUDFLARENET"]
        # Add random offset to each indexer's latitude and longitude, to avoid overlapping points
        for i, row in df.iterrows():
            df.loc[i, "latitude"] += .5 * random.uniform(-1, 1)
            df.loc[i, "longitude"] += .5 * random.uniform(-1, 1)

        # Initialize a Folium map centered on the average latitude and longitude
        mean_lat = df["latitude"].mean()
        mean_long = df["longitude"].mean()
        map_ = folium.Map(location=[mean_lat, mean_long], zoom_start=2)

        linear = cm.LinearColormap(["red", "yellow", "green"], index=[df['score'].min(), 950, df['score'].max()],
                                 vmin=df['score'].min(), vmax=df['score'].max())

        linear.caption = 'Indexer Score'
        map_.add_child(linear)

        # Plot the indexer points on the map, colored by their score
        for i, row in df.iterrows():
            folium.CircleMarker(
                location=[row["latitude"], row["longitude"]],
                radius=4,
                color=linear(row.score),
                fill=True,
                fill_color=linear(row.score),
                tooltip=f"{row['id']} - {row['score']} - {row['host']}"
            ).add_to(map_)

        # Save the map
        map_file = os.path.join(output_dir, f"indexer_map_{score_type}_{network}.html")
        map_.save(map_file)
        map_links.append((map_file, score_type, network))

    # Create an index file with links to the generated maps
    with open(os.path.join(output_dir, 'index.html'), 'w') as index_file:
        index_file.write('<html><head><title>Indexer Maps</title></head><body>')
        index_file.write('<h1>Indexer Maps</h1><ul>')
        for map_file, score_type, network in map_links:
            index_file.write(f'<li><a href="{os.path.basename(map_file)}">{score_type} - {network}</a></li>')
        index_file.write('</ul></body></html>')
