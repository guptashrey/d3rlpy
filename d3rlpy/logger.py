import numpy as np
import os
import json
import time

from typing import Any, Dict, List, Optional, Iterator
from contextlib import contextmanager
from tensorboardX import SummaryWriter
from datetime import datetime
from .base import LearnableBase


# default json encoder for numpy objects
def default_json_encoder(obj: Any) -> Any:
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError


class D3RLPyLogger:

    _experiment_name: str
    _logdir: str
    _save_metrics: bool
    _verbose: bool
    _metrics_buffer: Dict[str, List[float]]
    _params: Optional[Dict[str, float]]
    _writer: Optional[SummaryWriter]

    def __init__(
        self,
        experiment_name: str,
        save_metrics: bool = True,
        root_dir: str = "logs",
        verbose: bool = True,
        tensorboard: bool = True,
        with_timestamp: bool = True,
    ):
        self._save_metrics = save_metrics
        self._verbose = verbose

        # add timestamp to prevent unintentional overwrites
        while True:
            if with_timestamp:
                date = datetime.now().strftime("%Y%m%d%H%M%S")
                self._experiment_name = experiment_name + "_" + date
            else:
                self._experiment_name = experiment_name

            if self._save_metrics:
                self.logdir = os.path.join(root_dir, self._experiment_name)
                if not os.path.exists(self.logdir):
                    os.makedirs(self.logdir)
                    break
                else:
                    if with_timestamp:
                        time.sleep(1.0)
                    else:
                        raise ValueError("%s already exists." % self.logdir)
            else:
                break

        self._metrics_buffer = {}

        if tensorboard:
            tfboard_path = os.path.join("runs", self._experiment_name)
            self._writer = SummaryWriter(logdir=tfboard_path)
        else:
            self._writer = None

        self._params = None

    def add_params(self, params: Dict[str, Any]) -> None:
        assert self._params is None, "add_params can be called only once."

        if self._save_metrics:
            # save dictionary as json file
            with open(os.path.join(self._logdir, "params.json"), "w") as f:
                json_str = json.dumps(
                    params, default=default_json_encoder, indent=2
                )
                f.write(json_str)

        if self._verbose:
            for key, val in params.items():
                print("{}={}".format(key, val))

        # remove non-scaler values for HParams
        self._params = {k: v for k, v in params.items() if np.isscalar(v)}

    def add_metric(self, name: str, value: float) -> None:
        if name not in self._metrics_buffer:
            self._metrics_buffer[name] = []
        self._metrics_buffer[name].append(value)

    def commit(self, epoch: int, step: int) -> None:
        metrics = {}
        for name, buffer in self._metrics_buffer.items():
            metric = sum(buffer) / len(buffer)

            if self._save_metrics:
                with open(os.path.join(self._logdir, name + ".csv"), "a") as f:
                    print("%d,%d,%f" % (epoch, step, metric), file=f)

            if self._verbose:
                print("epoch=%d step=%d %s=%f" % (epoch, step, name, metric))

            if self._writer:
                self._writer.add_scalar("metrics/" + name, metric, epoch)

            metrics[name] = metric

        if self._params and self._writer:
            self._writer.add_hparams(
                self._params,
                metrics,
                name=self._experiment_name,
                global_step=epoch,
            )

        # initialize metrics buffer
        self._metrics_buffer = {}

    def save_model(self, epoch: int, algo: LearnableBase) -> None:
        if self._save_metrics:
            # save entire model
            model_path = os.path.join(self._logdir, "model_%d.pt" % epoch)
            algo.save_model(model_path)

    @contextmanager
    def measure_time(self, name: str) -> Iterator[None]:
        name = "time_" + name
        start = time.time()
        try:
            yield
        finally:
            self.add_metric(name, time.time() - start)
