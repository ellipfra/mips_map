# Indexer Maps

This script generates interactive maps of indexers based on different score types for the Goerli and Mainnet networks. The maps are generated as HTML files and are stored in the specified output directory. An index file containing links to all the generated maps is also created.

## Requirements

- Python 3.x
- Install the required Python packages: `pip install -r requirements.txt`

## Usage

1. Download the [GeoLite2 City](https://www.maxmind.com/en/geoip2-city) and [GeoLite2 ASN](https://www.maxmind.com/en/geoip2-asn) databases (requires a free MaxMind account). Extract the `.mmdb` files and place them in the project directory.

2. Run the script with the following command:

```
python indexer_maps.py --url <URL> --output-dir <OUTPUT_DIR>
```

- `<URL>` (optional): The URL of the leaderboard JSON data. Defaults to "https://thegraph.com/_next/data/1S8gjhHRAo46eQdAneE-H/migration-incentive-program/leaderboard.json".
- `<OUTPUT_DIR>` (optional): The output directory for the generated HTML files. Defaults to "output".

Alternatively, you can set the `URL` and `OUTPUT_DIR` environment variables instead of using command-line arguments.

## Output

The script generates HTML files for each score type and network combination in the specified output directory. An `index.html` file containing links to all the generated maps is also created.

## Customization

To customize the script, you can modify the following sections:

1. The `endpoints` dictionary to update or add network endpoints.
2. The `score_types` dictionary to update or add score types for each network.
