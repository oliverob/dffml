# Co-authored-by: John Andersen <johnandersenpdx@gmail.com>
# Co-authored-by: Soren Andersen <sorenpdx@gmail.com>
import pathlib
from typing import AsyncIterator
import importlib

import joblib
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score
import xgboost as xgb

from dffml.base import config, field
from dffml.model.accuracy import Accuracy
from dffml.model.model import SimpleModel, ModelNotTrained
from dffml.feature.feature import Feature, Features
from dffml.source.source import Sources
from dffml.util.entrypoint import entrypoint
from dffml.record import Record


# TODO Add parameters you want to have access to within self.config here
# For example, search for n_estimators to see how that works
@config
class XDGRegressorModelConfig:
    directory: pathlib.Path = field("Directory where model should be saved")
    features: Features = field("Features on which we train the model")
    predict: Feature = field("Value to be predicted")
    learning_rate: float = field("Learning rate to train with", default=0.1)
    n_estimators: int = field(
        "Number of graident boosted trees. Equivalent to the number of boosting rounds",
        default=1000,
    )


@entrypoint("xdgregressor")
class XDGRegressorModel(SimpleModel):
    CONFIG = XDGRegressorModelConfig

    def __init__(self, config) -> None:
        super().__init__(config)
        # The saved model
        self.saved = None
        self.np = importlib.import_module("numpy")
        self.saved_filepath = pathlib.Path(
            self.config.directory, "model.joblib"
        )
        # Load saved model if it exists
        if self.saved_filepath.is_file():
            self.saved = joblib.load(str(self.saved_filepath))

    async def train(self, sources: Sources) -> None:
        # Get data into memory
        xdata = []
        ydata = []
        async for record in sources.with_features(
            self.features + [self.parent.config.predict.name]
        ):
            record_data = []
            for feature in record.features(self.features).values():
                record_data.extend(
                    [feature] if self.np.isscalar(feature) else feature
                )
            xdata.append(record_data)
            ydata.append(record.feature(self.parent.config.predict.name))
        x_data = pd.DataFrame(xdata)
        y_data = pd.DataFrame(ydata)
        # XGBoost is a the leading software library for working with standard tabular data (the type of data you store in Pandas DataFrames,
        # as opposed to more exotic types of data like images and videos). With careful parameter tuning, you can train highly accurate models.
        # Parameters for xgboost
        #   n_estimators = 100-1000 range,
        #   learning_rate - In general, a small learning rate and large number of estimators will yield more accurate XGBoost models
        #       e.g. learning_rate=0.1
        #   n_jobs - specify number of cores to run in parallel
        # my_model = XGBRegressor()
        # my_model = XGBRegressor(n_estimators=1000)

        # TODO Tweak this?
        self.saved = xgb.XGBRegressor(
            n_estimators=self.config.n_estimators,
            learning_rate=self.config.learning_rate,
            max_depth=2,
            subsample=0.8,
        )
        # my_model = XGBRegressor(n_estimators=1000, learning_rate=0.05, n_jobs=4) *NOTE:  n_jobs made it slightly worse
        # print(x_data)
        # print(y_data)
        # TODO Tweak this?
        self.saved.fit(
            x_data, y_data, verbose=True,
        )

        # Save the trained model
        joblib.dump(self.saved, str(self.saved_filepath))

    async def accuracy(self, sources: Sources) -> Accuracy:
        if not self.saved:
            raise ModelNotTrained("Train the model before assessing accuracy")

        # Get data
        input_data = await self.getInputData(sources)

        # Make predictions
        xdata = []
        for record in input_data:
            record_data = []
            for feature in record.features(self.features).values():
                record_data.extend(
                    [feature] if self.np.isscalar(feature) else feature
                )
            xdata.append(record_data)

        predictions = self.saved.predict(pd.DataFrame(xdata))

        actuals = [
            input_datum.feature(self.config.predict.name)
            for input_datum in input_data
        ]

        # Calculate MAE

        # return mean_absolute_error(predictions, actuals)
        print(r2_score(actuals,predictions))
        return r2_score(actuals, predictions)

    async def predict(self, sources: Sources) -> AsyncIterator[Record]:
        if not self.saved:
            raise ModelNotTrained(
                "Train the model first before getting preictions"
            )
        # Grab records and input data (X data)
        input_data = await self.getInputData(sources)
        # Make predictions
        xdata = []
        for record in input_data:
            record_data = []
            for feature in record.features(self.features).values():
                record_data.extend(
                    [feature] if self.np.isscalar(feature) else feature
                )
            xdata.append(record_data)

        predictions = self.saved.predict(pd.DataFrame(xdata))
        # Update records and yield them to caller
        for record, prediction in zip(input_data, predictions):
            record.predicted(
                self.config.predict.name, float(prediction), float("nan")
            )
            yield record

    async def getInputData(self, sources: Sources) -> list:
        saved_records = []
        async for record in sources.with_features(
            self.config.features.names()
        ):
            saved_records.append(record)
        return saved_records
