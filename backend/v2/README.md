# v2 Domain Model

This package defines the normalized v2 core for statement imports.

- Parsers should produce `Transaction` objects only.
- Categories are flat records with stable `key` values.
- Classification rules reference `category_key`, not numeric IDs.
- A transaction has one canonical classification: `category_key`.

The legacy app can keep running while parser and UI layers are moved onto this model.
