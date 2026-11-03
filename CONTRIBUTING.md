# Contribute to EML

Collaborators can propose an exercise as a pull request containing one JSON file. Use the file's stable ID as its name. Include the setup, apparatus and grip, phased path, repetition or hold, and muscle roles. A new ID can use an existing macro, define a local variation, or compose joints and constraints directly. Author exercise-specific changes locally first. Shared macros and equipment definitions belong in the registry when other exercises can reuse them.

For an exercise PR, state what the user should see at setup, at the most demanding phase, and at the rep boundary. Run the tests below and attach a viewer capture when changing visible movement. Include a mechanical assertion for a quality that could otherwise regress, such as feet remaining planted while a loaded arm extends. Review authorship and rights before contributing outside assets.

For a language or registry change, describe the use case and why the current sockets cannot express it. Provide a positive example, an incompatible or impossible example with the expected diagnostic, and any migration rule. Update the schema, interpretation, reference player and contributor-facing interface together. An existing stable exercise ID should continue to identify the same exercise. Maintainers review proposals and merge tested changes. Ordinary vocabulary and catalog additions can be proposed without a new schema version.

```sh
python -m unittest discover -s tests -v
python -m eml catalog -o out/catalog-report.json
python -m eml validate examples/paused-goblet-look-left.json
```

Code, schemas and original exercise descriptions use the repository's MIT license. The anatomy asset and its derivatives have separate attribution and share-alike terms in [anatomy/ATTRIBUTION.md](anatomy/ATTRIBUTION.md). Keep those notices with redistributed assets.
