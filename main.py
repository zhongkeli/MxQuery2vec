# -*- coding: utf-8 -*-
"""
Sequence 2 sequence for Query2Vec

"""

import logging
import yaml
import yamlordereddictloader
import os
import clg
import time
from conf.customYamlType import IntegerType, LoggerLevelType
import argparse


# sys.path.append('.')
# sys.path.append('..')

def parse_args():
    parser = argparse.ArgumentParser(description='Train Seq2seq model for query2vec')
    subparsers = parser.add_subparsers(help='train or test')

    train_parser = subparsers.add_parser("train")
    test_parser = subparsers.add_parser("test")

    train_parser.add_argument('-sny', '--source-num-layers', default=1, type=int,
                        help='number of layers for the LSTM recurrent neural network')
    train_parser.add_argument('-snh', '--source-num-hidden', default=10, type=int,
                        help='number of hidden units in the neural network')
    train_parser.add_argument('-bs', '--batch-size', default=2, type=int,
                        help='batch size for each databatch')
    train_parser.add_argument('--iterations', default=1, type=int,
                        help='number of iterations (epoch)')
    train_parser.add_argument('-mp', '--model-prefix', default=os.path.join(os.getcwd(), 'model', 'query2vec'), type=str,
                        help='the experiment name, this is also the prefix for the parameters file')
    train_parser.add_argument('-pd', '--params-dir', default='params', type=str,
                        help='the directory to store the parameters of the training')
    train_parser.add_argument('--gpus', type=str,
                        help='the gpus will be used, e.g "0,1,2,3"')
    train_parser.add_argument('enc_train_input', type=str,
                        help='the file name of the encoder input for training')
    train_parser.add_argument('dec_train_input', type=str,
                        help='the file name of the decoder input for training')
    train_parser.add_argument('-eti', '--enc-test-input', type=str,
                        help='the file name of the encoder input for testing')
    train_parser.add_argument('-dti', '--dec-test-input', type=str,
                        help='the file name of the decoder input for testing')
    train_parser.add_argument('-do', '--dropout', default=0.0, type=float,
                        help='dropout is the probability to ignore the neuron outputs')
    train_parser.add_argument('-tw', '--top-words', default=80, type=int,
                        help='the top percentile of word count to retain in the vocabulary')
    train_parser.add_argument('-lf', '--log-freq', default=1000, type=int,
                        help='the frequency to printout the training verbose information')
    train_parser.add_argument('-lr', '--learning-rate', default=0.01, type=float,
                        help='learning rate of the stochastic gradient descent')
    train_parser.add_argument('-le', '--load-epoch', dest='load_epoch', help='epoch of pretrained model',
                        default=0, type=int)
    train_parser.add_argument('-ne', '--num-epoch', dest='num_epoch', help='end epoch of query2vec training',
                        default=100000, type=int)
    train_parser.add_argument('-kv', '--kv-store', dest='kv_store', help='the kv-store type',
                        default='device', type=str)
    train_parser.add_argument('-wll', '--work-load_-ist', dest='work_load_list', help='work load for different devices',
                        default=None, type=list)
    train_parser.add_argument('-mom', '--momentum', type=float, default=0.9, help='momentum for sgd')
    train_parser.add_argument('-wd','--weight-decay', type=float, default=0.0005, help='weight decay for sgd')
    train_parser.add_argument('--factor-step', type=int, default=50000, help='the step used for lr factor')
    train_parser.add_argument('--monitor', action='store_true', default=False,
                        help='if true, then will use monitor debug')
    train_parser.add_argument('-b', '--bucket', nargs=2, action='append')
    files = parser.parse_args().bucket

    for f in files:
        print tuple(f)
    args = parser.parse_args()
    return args


def parseArgs(config_path):
    clg.TYPES.update({'Integer': IntegerType, 'LoggerLevel': LoggerLevelType})
    cmd = clg.CommandLine(yaml.load(open(config_path),
                                    Loader=yamlordereddictloader.Loader))
    args = cmd.parse()

    logging.basicConfig(format='%(asctime)s %(levelname)s:%(name)s:%(message)s', level=args.loglevel,
                        datefmt='%H:%M:%S')
    file_handler = logging.FileHandler(os.path.join(args.logdir, time.strftime("%Y%m%d-%H%M%S") + '.logs'))
    file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)-5.5s:%(name)s] %(message)s'))
    logging.root.addHandler(file_handler)

    for arg, value in args:
        print("  %s: %s" % (arg, value))
    return args


if __name__ == "__main__":
    args = parseArgs('./conf/config.yml')
    if args.command0 == 'train':
        logging.info('In train mode.')
        from model.trainer import trainer

        trainer(train_source_path=args.train_source_path, train_target_path=args.train_target_path,
                vocabulary_path=args.vocabulary_path) \
            .set_model_parameter(s_layer_num=args.s_layer_num, s_hidden_unit=args.s_hidden_unit,
                                 s_embed_size=args.s_embed_size, t_layer_num=args.t_layer_num,
                                 t_hidden_unit=args.t_hidden_unit, t_embed_size=args.t_embed_size, buckets=args.buckets) \
            .set_train_parameter(s_dropout=args.s_dropout, t_dropout=args.t_dropout, load_epoch=args.load_epoch,
                                 model_prefix=args.model_prefix, device_model=args.device_model, devices=args.devices,
                                 lr_factor=args.lr_factor, \
                                 lr=args.lr, train_max_samples=args.train_max_samples, momentum=args.momentum,
                                 show_every_x_batch=args.show_every_x_batch, num_epoch=args.num_epoch,
                                 optimizer=args.optimizer, batch_size=args.batch_size) \
            .set_mxnet_parameter(loglevel=args.loglevel, kv_store=args.kv_store, monitor_interval=args.monitor_interval) \
            .train()
    elif args.command0 == 'vocab':
        from vocabulary.vocab_gen import vocab

        vocab(args.files, args.vocab_file_path, args.most_commond_words_file_path, special_words=args.special_words,
              logdir=args.logdir) \
            .create_dictionary()
