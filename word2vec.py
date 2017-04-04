# -*- coding: utf-8 -*-
"""
Sequence 2 sequence for Query2Vec

"""

import os
import sys
from argparser.customArgType import DirectoryType
import argparse
from utils.log_util import set_up_logger_handler_with_file
import logging
import signal


def parse_args():
    parser = argparse.ArgumentParser(description='Train Seq2seq query2vec for query2vec')
    parser.add_argument('--log-conf-path', default=os.path.join(os.getcwd(), 'configure', 'logger.conf'),
                        type=DirectoryType, help='Log directory (default: __DEFAULT__).')
    parser.add_argument('--log-qualname', choices=['root', 'query2vec', 'seq2seq_data_zmq'],
                        default='root',
                        help='Log qualname on console (default: __DEFAULT__).')
    subparsers = parser.add_subparsers(help='train vocabulary')
    w2v_trainer_parser = subparsers.add_parser("train_word2vec")
    w2v_trainer_parser.set_defaults(action='train_word2vec')
    w2v_dumper_parser = subparsers.add_parser("dump_word2vec")
    w2v_dumper_parser.set_defaults(action='dump_word2vec')


    # word2vec parameter

    # mxnet parameter
    w2v_trainer_parser.add_argument('-dm', '--device-mode', choices=['cpu', 'gpu', 'gpu_auto'],
                                    help='define define mode, (default: %(default)s)',
                                    default='cpu')
    w2v_trainer_parser.add_argument('-d', '--devices', type=str, default='0',
                                    help='the devices will be used, e.g "0,1,2,3"')

    w2v_trainer_parser.add_argument('-lf', '--log-freq', default=1000, type=int,
                                    help='the frequency to printout the training verbose information')

    w2v_trainer_parser.add_argument('-scf', '--save-checkpoint-freq', default=1, type=int,
                                    help='the frequency to save checkpoint')

    w2v_trainer_parser.add_argument('-kv', '--kv-store', dest='kv_store', help='the kv-store type',
                                    default='local', type=str)
    w2v_trainer_parser.add_argument('-mi', '--monitor-interval', default=0, type=int,
                                    help='log network parameters every N iters if larger than 0')
    w2v_trainer_parser.add_argument('-eval', '--enable-evaluation', action='store_true', help='enable evaluation')

    w2v_trainer_parser.add_argument('-wll', '--work-load-ist', dest='work_load_list',
                                    help='work load for different devices',
                                    default=None, type=list)
    w2v_trainer_parser.add_argument('--hosts-num', dest='hosts_num', help='the number of the hosts',
                                    default=1, type=int)
    w2v_trainer_parser.add_argument('--workers-num', dest='workers_num', help='the number of the workers',
                                    default=1, type=int)
    w2v_trainer_parser.add_argument('-db', '--disp-batches', dest='disp_batches',
                                    help='show progress for every n batches',
                                    default=1, type=int)
    w2v_trainer_parser.add_argument('-le', '--load-epoch', dest='load_epoch', help='epoch of pretrained model',
                                    type=int, default=-1)
    w2v_trainer_parser.add_argument('-r', '--rank', dest='rank', help='epoch of pretrained model',
                                    type=int, default=0)
    w2v_trainer_parser.add_argument('-mp', '--model-prefix', default='word2vec',
                                    type=str,
                                    help='the experiment name, this is also the prefix for the parameters file')
    w2v_trainer_parser.add_argument('-pd', '--model-path',
                                    default=os.path.join(os.getcwd(), 'data', 'word2vec', 'model'),
                                    type=DirectoryType,
                                    help='the directory to store the parameters of the training')

    # optimizer parameter
    w2v_trainer_parser.add_argument('-opt', '--optimizer', type=str, default='AdaGrad',
                                    help='the optimizer type')
    w2v_trainer_parser.add_argument('-cg', '--clip-gradient', type=float, default=5.0,
                                    help='clip gradient in range [-clip_gradient, clip_gradient]')
    w2v_trainer_parser.add_argument('--wd', type=float, default=0.00001,
                                    help='weight decay for sgd')
    w2v_trainer_parser.add_argument('--mom', dest='momentum', type=float, default=0.9,
                                    help='momentum for sgd')
    w2v_trainer_parser.add_argument('--lr', dest='learning_rate', type=float, default=0.01,
                                    help='initial learning rate')

    # model parameter
    w2v_trainer_parser.add_argument('-bs', '--batch-size', default=128, type=int,
                                    help='batch size for each databatch')
    w2v_trainer_parser.add_argument('-es', '--embed-size', default=128, type=int,
                                    help='embedding size ')
    w2v_trainer_parser.add_argument('-ws', '--window-size', default=2, type=int,
                                    help='window size ')

    # word2vec data parameter
    w2v_trainer_parser.add_argument('corpus_data_path', type=str,
                                    help='the file name of the corpus')
    w2v_trainer_parser.add_argument('vocabulary_save_path', type=str,
                                    help='the file name of the corpus')

    # word2vec dumper parameter
    w2v_dumper_parser.add_argument('-mp', '--model-prefix', default='word2vec',
                                   type=str,
                                   help='the experiment name, this is also the prefix for the parameters file')
    w2v_dumper_parser.add_argument('-pd', '--model-path',
                                   default=os.path.join(os.getcwd(), 'data', 'word2vec', 'model'),
                                   type=DirectoryType,
                                   help='the directory to store the parameters of the training')
    w2v_dumper_parser.add_argument('-r', '--rank', default=0,
                                   type=int,
                                   help='the experiment name, this is also the prefix for the parameters file')

    w2v_dumper_parser.add_argument('-le', '--load-epoch', dest='load_epoch', help='epoch of pretrained model',
                                   type=int, default=1)
    w2v_dumper_parser.add_argument('w2v_vocabulary_path', type=str,
                                   help='the file name of the corpus')
    w2v_dumper_parser.add_argument('w2v_save_path', type=str,
                                   help='the file name of the corpus')

    return parser.parse_args()


def signal_handler(signal, frame):
    logging.info('Stop!!!')
    sys.exit(0)


def set_up_logger():
    set_up_logger_handler_with_file(args.log_conf_path, args.log_qualname)


if __name__ == "__main__":
    args = parse_args()
    set_up_logger()
    print(args)
    signal.signal(signal.SIGINT, signal_handler)
    if args.action == 'train_word2vec':
        from word2vec.word2vec_trainer import Word2vecTrainer, mxnet_parameter, optimizer_parameter, model_parameter

        mxnet_para = mxnet_parameter(kv_store=args.kv_store, hosts_num=args.hosts_num, workers_num=args.workers_num,
                                     device_mode=args.device_mode, devices=args.devices,
                                     disp_batches=args.disp_batches, monitor_interval=args.monitor_interval,
                                     save_checkpoint_freq=args.save_checkpoint_freq,
                                     model_path_prefix=os.path.join(args.model_path, args.model_prefix),
                                     enable_evaluation=args.enable_evaluation,
                                     load_epoch=args.load_epoch)

        optimizer_para = optimizer_parameter(optimizer=args.optimizer, learning_rate=args.learning_rate, wd=args.wd,
                                             momentum=args.momentum)

        model_para = model_parameter(embed_size=args.embed_size, batch_size=args.batch_size,
                                     window_size=args.window_size)
        Word2vecTrainer(data_path=args.corpus_data_path, vocabulary_save_path=args.vocabulary_save_path,
                        mxnet_para=mxnet_para,
                        optimizer_para=optimizer_para,
                        model_para=model_para).train()
    elif args.action == 'dump_word2vec':
        from word2vec.word2vec_dumper import W2vDumper

        W2vDumper(w2v_model_path=os.path.join(args.model_path, args.model_prefix), vocab_path=args.w2v_vocabulary_path,
                  w2v_save_path=args.w2v_save_path, rank=args.rank, load_epoch=args.load_epoch).dumper()

