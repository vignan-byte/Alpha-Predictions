# Model artifacts

Trained `.joblib` files are deployment artifacts, not guarantees of future performance. Every artifact must be accompanied by its metadata JSON and checked for feature-version compatibility before inference.

The application can safely start without an active model. In that case it reports **NO VALIDATED MODEL** rather than fabricating a forecast.

Before a seminar or production deployment, train or import a model using the exact market/data source you intend to demonstrate, verify the validation report, and record the model version in your release notes.
