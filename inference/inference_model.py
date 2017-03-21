import mxnet as mx
from network.rnn.lstm import lstm, LSTMParam, LSTMState
from network.seq2seq.encoder import BiDirectionalLstmEncoder, LstmEncoder
from network.attention.soft_attention import SoftAttention


def initial_state_symbol(decoder_layer_num, decoder_hidden_unit_num):
    encoded = mx.sym.Variable("encoded")
    init_weight = mx.sym.Variable("decoder_init_weight")
    init_bias = mx.sym.Variable("decoder_init_bias")
    init_h = mx.sym.FullyConnected(data=encoded, num_hidden=decoder_hidden_unit_num * decoder_layer_num,
                                   weight=init_weight, bias=init_bias, name='init_fc')
    init_h = mx.sym.Activation(data=init_h, act_type='tanh', name='init_act')
    init_hs = mx.sym.SliceChannel(data=init_h, num_outputs=decoder_layer_num)
    return init_hs


class BiSeq2seqInferenceModel(object):
    def __init__(self, encoder_layer_num, encoder_seq_len, encoder_vocab_size, encoder_hidden_unit_num,
                 encoder_embed_size,
                 encoder_dropout,
                 decoder_layer_num, decoder_vocab_size, decoder_hidden_unit_num, decoder_embed_size, decoder_dropout,
                 arg_params,
                 use_masking, ctx=mx.cpu(),
                 batch_size=1):

        self.decoder_layer_num = decoder_layer_num

        self.encoder_sym = bidirectional_encoder_symbol(encoder_layer_num, encoder_seq_len, use_masking,
                                                        encoder_vocab_size, encoder_hidden_unit_num, encoder_embed_size,
                                                        encoder_dropout)
        attention = SoftAttention(seq_len=encoder_seq_len, encoder_hidden_output_dim=encoder_hidden_unit_num * 2,
                                   state_dim=decoder_hidden_unit_num)
        self.decoder_sym = lstm_attention_decoder_symbol(encoder_seq_len, decoder_layer_num, decoder_vocab_size, decoder_hidden_unit_num,
                                               decoder_embed_size,
                                               decoder_dropout, attention)
        self.init_state_sym = initial_state_symbol(decoder_layer_num, decoder_hidden_unit_num)

        # initialize states for LSTM
        forward_encoder_init_c = [('forward_encoder_l%d_init_c' % l, (batch_size, encoder_hidden_unit_num)) for l in
                                  xrange(encoder_layer_num)]
        forward_encoder_init_h = [('forward_encoder_l%d_init_h' % l, (batch_size, encoder_hidden_unit_num)) for l in
                                  xrange(encoder_layer_num)]
        backward_encoder_init_c = [('backward_encoder_l%d_init_c' % l, (batch_size, encoder_hidden_unit_num)) for l in
                                   xrange(encoder_layer_num)]
        backward_encoder_init_h = [('backward_encoder_l%d_init_h' % l, (batch_size, encoder_hidden_unit_num)) for l in
                                   xrange(encoder_layer_num)]
        encoder_init_states = forward_encoder_init_c + forward_encoder_init_h + backward_encoder_init_c + backward_encoder_init_h

        decoder_init_c = [('decoder_l%d_init_c' % l, (batch_size, decoder_hidden_unit_num)) for l in
                          xrange(decoder_layer_num)]
        decoder_init_h = [('decoder_l%d_init_h' % l, (batch_size, decoder_hidden_unit_num)) for l in
                          xrange(decoder_layer_num)]
        decoder_init_states = decoder_init_c + decoder_init_h

        encoder_data_shape = [("encoder_data", (batch_size, encoder_seq_len))]
        encoder_mask_data_shape = [("encoder_mask", (batch_size, encoder_seq_len))]
        decoder_data_shape = [("decoder_data", (batch_size,))]
        attend_state_shapes = [("attended", (batch_size, encoder_hidden_unit_num * 2 * encoder_seq_len))]
        init_state_shapes = [("encoded", (batch_size, encoder_hidden_unit_num * 2))]

        encoder_input_shapes = dict(encoder_init_states + encoder_data_shape + encoder_mask_data_shape)
        decoder_input_shapes = dict(decoder_init_states + decoder_data_shape + attend_state_shapes)
        init_input_shapes = dict(init_state_shapes)

        self.encoder_executor = self.encoder_sym.simple_bind(ctx=ctx, grad_req='null', **encoder_input_shapes)
        self.decoder_executor = self.decoder_sym.simple_bind(ctx=ctx, grad_req='null', **decoder_input_shapes)
        self.init_state_executor = self.init_state_sym.simple_bind(ctx=ctx, grad_req='null', **init_input_shapes)

        for key in self.encoder_executor.arg_dict.keys():
            if key in arg_params:
                arg_params[key].copyto(self.encoder_executor.arg_dict[key])
        for key in self.decoder_executor.arg_dict.keys():
            if key in arg_params:
                arg_params[key].copyto(self.decoder_executor.arg_dict[key])
        for key in self.init_state_executor.arg_dict.keys():
            if key in arg_params:
                arg_params[key].copyto(self.init_state_executor.arg_dict[key])

        encoder_state_name = []
        for i in range(encoder_layer_num):
            encoder_state_name.append("forward_encoder_l%d_init_c" % i)
            encoder_state_name.append("forward_encoder_l%d_init_h" % i)
            encoder_state_name.append("backward_encoder_l%d_init_c" % i)
            encoder_state_name.append("backward_encoder_l%d_init_h" % i)

        self.encoder_state_name = encoder_state_name

    def encode(self, input_data, input_mask):
        for key in self.encoder_state_name:
            self.encoder_executor.arg_dict[key][:] = 0.
        input_data.copyto(self.encoder_executor.arg_dict["encoder_data"])
        input_mask.copyto(self.encoder_executor.arg_dict["encoder_mask"])
        self.encoder_executor.forward()
        last_encoded = self.encoder_executor.outputs[0]
        all_encoded = self.encoder_executor.outputs[1]
        return last_encoded, all_encoded

    def decode_forward(self, last_encoded, all_encoded, input_data, new_seq):
        if new_seq:
            last_encoded.copyto(self.init_state_executor.arg_dict["encoded"])
            all_encoded.copyto(self.decoder_executor.arg_dict["attended"])
            self.init_state_executor.forward()
            for i in xrange(self.decoder_layer_num):
                init_hs = self.init_state_executor.outputs[i]
                init_hs.copyto(self.decoder_executor.arg_dict["decoder_l%d_init_h" % i])
                self.decoder_executor.arg_dict["decoder_l%d_init_c" % i][:] = 0.0
        input_data.copyto(self.decoder_executor.arg_dict["decoder_data"])
        self.decoder_executor.forward()

        prob = self.decoder_executor.outputs[0].asnumpy()
        # print(prob)
        for i in xrange(1, self.decoder_layer_num * 2, 2):
            self.decoder_executor.outputs[i].copyto(self.decoder_executor.arg_dict["decoder_l%d_init_h" % (i/2)])
            self.decoder_executor.outputs[i+1].copyto(self.decoder_executor.arg_dict["decoder_l%d_init_c" % (i/2)])
        return prob


def bidirectional_encoder_symbol(encoder_layer_num, encoders_seq_len, use_masking, encoder_vocab_size,
                                 encoder_hidden_unit_num, encoder_embed_size,
                                 s_dropout):
    embed_weight = mx.sym.Variable("share_embed_weight")
    encoder = BiDirectionalLstmEncoder(seq_len=encoders_seq_len, use_masking=use_masking,
                                       hidden_unit_num=encoder_hidden_unit_num,
                                       vocab_size=encoder_vocab_size, embed_size=encoder_embed_size,
                                       dropout=s_dropout, layer_num=encoder_layer_num, embed_weight=embed_weight)
    forward_hidden_all, backward_hidden_all, bi_hidden_all, _ = encoder.encode()
    concat_encoded = mx.sym.Concat(*bi_hidden_all, dim=1)
    decoded_init_state = mx.sym.Concat(forward_hidden_all[-1], backward_hidden_all[0], dim=1,
                                       name='decoded_init_state')
    return mx.sym.Group([decoded_init_state, concat_encoded])


def lstm_attention_decoder_symbol(encoder_seq_len, decoder_layer_num, decoder_vocab_size, decoder_hidden_unit_num, decoder_embed_size,
                        decoder_dropout, attention):
    data = mx.sym.Variable("decoder_data")
    seqidx = 0

    embed_weight = mx.sym.Variable("share_embed_weight")
    cls_weight = mx.sym.Variable("decoder_cls_weight")
    cls_bias = mx.sym.Variable("decoder_cls_bias")

    input_weight = mx.sym.Variable("decoder_input_weight")
    # input_bias = mx.sym.Variable("target_input_bias")

    param_cells = []
    last_states = []

    for i in range(decoder_layer_num):
        param_cells.append(LSTMParam(i2h_weight=mx.sym.Variable("decoder_l%d_i2h_weight" % i),
                                     i2h_bias=mx.sym.Variable("decoder_l%d_i2h_bias" % i),
                                     h2h_weight=mx.sym.Variable("decoder_l%d_h2h_weight" % i),
                                     h2h_bias=mx.sym.Variable("decoder_l%d_h2h_bias" % i)))
        state = LSTMState(c=mx.sym.Variable("decoder_l%d_init_c" % i),
                          h=mx.sym.Variable("decoder_l%d_init_h" % i))
        # state = LSTMState(c=mx.sym.Variable("target_l%d_init_c" % i),
        #                   h=init_hs[i])
        last_states.append(state)
    assert (len(last_states) == decoder_layer_num)

    hidden = mx.sym.Embedding(data=data,
                              input_dim=decoder_vocab_size,
                              output_dim=decoder_embed_size,
                              weight=embed_weight,
                              name="decoder_embed")

    all_encoded = mx.sym.Variable("attended")
    all_attended = mx.sym.Reshape(data=all_encoded, shape=(1, encoder_seq_len, -1),
                                  name='_reshape_concat_attended')
    encoded = mx.sym.SliceChannel(data=all_encoded, axis=1, num_outputs=encoder_seq_len)
    weighted_encoded = attention.attend(encoder_hidden_all=encoded, concat_attended=all_attended,
                                                 state=last_states[0].h,
                                                 attend_masks=None,
                                                 use_masking=False)
    con = mx.sym.Concat(hidden, weighted_encoded)
    hidden = mx.sym.FullyConnected(data=con, num_hidden=decoder_embed_size,
                                    no_bias=True, weight=input_weight, name='input_fc')
    # hidden = mx.sym.Activation(data=hidden, act_type='tanh', name='input_act')

    # stack LSTM
    for i in range(decoder_layer_num):
        if i == 0:
            dp = 0.
        else:
            dp = decoder_dropout
        next_state = lstm(decoder_hidden_unit_num, indata=hidden,
                          prev_state=last_states[i],
                          param=param_cells[i],
                          seqidx=seqidx, layeridx=i, dropout=dp)
        hidden = next_state.h
        last_states[i] = next_state

    fc = mx.sym.FullyConnected(data=hidden, num_hidden=decoder_vocab_size,
                               weight=cls_weight, bias=cls_bias, name='decoder_pred')
    sm = mx.sym.SoftmaxOutput(data=fc, name='decoder_softmax')
    output = [sm]
    for state in last_states:
        output.append(state.c)
        output.append(state.h)
    return mx.sym.Group(output)