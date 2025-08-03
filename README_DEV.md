# Notes for Local Development

- use python `3.9.x` (works with `3.9.19`)
- to downgrade `protobuf` version if it has problem
- add `dotenv` in `config.py` to load variables from `.env` file
  ```
    import os
    from dotenv import load_dotenv
    load_dotenv()
  ```
- update `main.py` with commenting `try` block and setting
  - `maptable = None`
  - `scaffoldtable = None`
  - `featuredDatasetIdSelectorTable = None`
- Contentful CDA client error (401) might be from invalid access token
