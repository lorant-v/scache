## Handling manifest 
- Simplest approach would be to use a single model for Secret/Output/Manifest
- Allowing user to define a default_provider creates inheritance between the 
  secret.provider and default_provider which needs to be resolved
- Ideally the application should not need to care about looking for the "correct"
  provider for a secret. This could be done at the provider grouping step but it leaks
  responsibility outside of the Manifest.
- In order to keep this normalization step a Manifest concern, we could
  1. Parse and modify the .secrets in json before dataclass conversion
  2. Modify .secrets after dataclass conversion (in place)
  3. Create a "resolved"/app model, which is separate from the user model.
- Initially option 2 was implemented, but a dataclass needs to be frozen in order for it
  to be hashable, thus used as a key in a dict. This is not strictly necessary but makes
  the split of responsibilities cleaner.
- Switched over to option 3, which requires more maintenance in case of a Manifest
  change (rare) but brings the benefit of a clear separation between the user model and
  the app model