from wordvec_model import Word2vec
import mxnet as mx
from utils.decorator_util import memoized
from utils.device_util import get_devices
from metric.word2vec_metric import NceAuc
from metric.speedometer import Speedometer
from word2vec_io import Word2vecDataIter
from utils.model_util import load_model, save_model, init_log
import logging
from itertools import chain
from base.trainer import Trainer
from utils.record_type import RecordType

"""mxnet parameter
Parameter:
    kv_store: str, the type of KVStore
        - local works for multiple devices on a single machine (single process)
        - dist works for multi-machines (multiple processes)
    hosts_num: int
        the number of hosts
    workers_num: int
        the number of workers
    device_mode: str
        device mode, ['cpu', 'gpu', 'gpu_auto']
    devices: str
        the devices will be used, e.g "0,1,2,3"
    num_epoch: int
        end epoch of model training
    disp_batches: int
        show progress for every n batches
    monitor_interval: int
        Number of batches between printing. if monitor_interval < 0, disabale  monitor
    log_level: log level
    log_path: str
        path to store log
    save_checkpoint_freq: int
        the frequency to save checkpoint
    enable_evaluation: boolean
        whether to enable evaluation
    load_epoch: int
        epoch of pretrained model, if load_epoch < 0, create new model to train
    model_path_prefix: str
        word2vec model path prefix
"""

mxnet_parameter = RecordType('mxnet_parameter',
                             [('kv_store', 'local'), ('hosts_num', 1), ('workers_num', 1), ('device_mode', 'cpu'),
                              ('devices', '0'), ('num_epoch', 65535), ('disp_batches', 1), ('monitor_interval', 2),
                              ('log_level', logging.ERROR), ('log_path', './logs'), ('save_checkpoint_freq', 1),
                              ('model_path_prefix', 'word2vec'), ('enable_evaluation', False), ('load_epoch', 1)])
"""optimizer parameter
Parameter:
    optimizer: str
        optimizer method, e.g. Adadelta, sgd
    clip_gradient: float
        clip gradient in range [-clip_gradient, clip_gradient]
    rescale_grad: float
        rescaling factor of gradient. Normally should be 1/batch_size.
    learning_rate: float
        learning rate of the stochastic gradient descent
    momentum: float
        momentum for sgd
    wd: float
        weight decay
"""

optimizer_parameter = RecordType('optimizer_parameter',
                                 [('optimizer', 'Adadelta'), ('clip_gradient', 5.0), ('rescale_grad', -1.0),
                                  ('learning_rate', 0.01), ('wd', 0.0005), ('momentum', 0.9)])

"""model parameter
Parameter:
    embed_size: int
       word embedding size
    window_size: int
       context window size
    batch_size: int
        batch size for each databatch
"""
model_parameter = RecordType('model_parameter', [('embed_size', 128), ('batch_size', 128), ('window_size', 2)])


class Word2vecTrainer(Trainer):
    def __init__(self, data_path, vocabulary_save_path, mxnet_para=mxnet_parameter, optimizer_para=optimizer_parameter,
                 model_para=model_parameter):
        super(Word2vecTrainer, self).__init__(mxnet_para=mxnet_para, optimizer_para=optimizer_para,
                                               model_para=model_para)
        self.data_path = data_path  # ./data/word2vec/train.dec
        self.vocabulary_save_path = vocabulary_save_path

    @property
    @memoized
    def ctx_devices(self):
        """return devices"""
        devs = get_devices(self.devices, self.device_mode, self.kv.rank, self.hosts_num, self.workers_num)
        return devs

    @property
    def network_symbol(self):
        sym = Word2vec(self.batch_size, self.data_loader.vocab_size, self.embed_size, self.window_size).network_symbol()
        return sym

    @property
    @memoized
    def train_data_loader(self):
        # build data iterator
        data_loader = Word2vecDataIter(self.data_path, self.vocabulary_save_path, self.batch_size,
                                       2 * self.window_size + 1)
        return data_loader

    @property
    def eval_data_loader(self):
        return None

    def train(self):
        network_symbol = self.network_symbol
        devices = self.ctx_devices
        data_loader = self.train_data_loader

        # load model
        sym, arg_params, aux_params = load_model(self.model_path_prefix, self.kv.rank, self.load_epoch)
        # save model
        checkpoint = save_model(self.model_path_prefix, self.kv.rank, self.save_checkpoint_freq)

        # set initializer to initialize the module parameters
        initializer = mx.init.Xavier(
            rnd_type='gaussian', factor_type="in", magnitude=2)
        model = mx.mod.Module(context=devices,
                              symbol=network_symbol, data_names=self.train_data_loader.data_names,
                              label_names=self.train_data_loader.label_names)

        # callbacks that run after each batch
        batch_end_callbacks = [Speedometer(self.batch_size, self.kv.rank, self.disp_batches)]

        metric = NceAuc()
        model.fit(data_loader,
                  eval_metric=metric,
                  initializer=initializer,
                  num_epoch=self.num_epoch,
                  batch_end_callback=batch_end_callbacks,
                  epoch_end_callback=checkpoint,
                  kvstore=self.kv,
                  optimizer=self.optimizer,
                  optimizer_params=self.optimizer_params,
                  arg_params=arg_params,
                  aux_params=aux_params,
                  )
