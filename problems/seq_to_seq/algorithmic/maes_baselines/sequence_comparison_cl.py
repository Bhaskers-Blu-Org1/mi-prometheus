# Add path to main project directory - required for testing of the main function and see whether problem is working at all (!)
import os,  sys
sys.path.append(os.path.join(os.path.dirname(__file__),  '..','..','..','..')) 

import torch
import numpy as np
from problems.problem import DataTuple
from problems.seq_to_seq.algorithmic.algorithmic_seq_to_seq_problem import AlgorithmicSeqToSeqProblem, AlgSeqAuxTuple


class SequenceComparisonCommandLines(AlgorithmicSeqToSeqProblem):
    """
    Class generating sequences of random bit-patterns and targets forcing the system to learn scratch pad problem (overwrite the memory).

    @Ryan: ARE YOU SURE? FIX THE CLASS DESCRIPTION!
    """

    def __init__(self, params):
        """ 
        Constructor - stores parameters. Calls parent class initialization.
        
        :param params: Dictionary of parameters.
        """
        # Call parent constructor - sets e.g. the loss function ;)
        super(SequenceComparisonCommandLines, self).__init__(params)
        
        # Retrieve parameters from the dictionary.
        self.batch_size = params['batch_size']
        # Number of bits in one element.
        self.control_bits = params['control_bits']
        self.data_bits = params['data_bits']
        assert self.control_bits >=3, "Problem requires at least 3 control bits (currently %r)" % self.control_bits
        assert self.data_bits >=1, "Problem requires at least 1 data bit (currently %r)" % self.data_bits
        # Min and max lengts (number of elements).
        self.min_sequence_length = params['min_sequence_length']
        self.max_sequence_length = params['max_sequence_length']
        # Parameter  denoting 0-1 distribution (0.5 is equal).
        self.bias = params['bias']
        self.dtype = torch.FloatTensor

    def generate_batch(self):
        """Generates a batch  of size [BATCH_SIZE, SEQ_LENGTH, CONTROL_BITS+DATA_BITS].
        SEQ_LENGTH depends on number of sub-sequences and its lengths
       
        :returns: Tuple consisting of: input, output and mask
                  pattern of inputs: x1, x2, ...xn d
                  pattern of target: d, d,   ...d xn
                  mask: used to mask the data part of the target
                  xi, d: sub sequences, dummies

        TODO: deal with batch_size > 1
        """
        # define control channel markers
        pos = [0, 0, 0]
        ctrl_data = [0, 0, 0]
        ctrl_dummy = [0, 0, 1]
        ctrl_inter = [0, 1, 0]
        #ctrl_y = [0, 0, 1]
        ctrl_start = [1, 0, 0]
        ctrl_output = [1, 1, 1]
        # assign markers
        markers = ctrl_data, ctrl_dummy, pos

        # number sub sequences
        #num_sub_seq = np.random.randint(self.num_subseq_min, self.num_subseq_max+1)
        #num_sub_seq = np.random.randint(self.num_subseq_min, self.num_subseq_max+1)

        # set the sequence length of each marker
        seq_length = np.random.randint(low=self.min_sequence_length, high=self.max_sequence_length + 1)

        #  generate subsequences for x and y
        x = [np.array(np.random.binomial(1, self.bias, (self.batch_size, seq_length, self.data_bits)))] 

        # Generate the second sequence which is either a scrambled version of the first
        # or exactly identical with approximately 50% probability (technically the scrambling
        # allows them to be the same with a very low chance)

        # First generate a random binomial of the same size as x, this will be used be used with an xor operation to scamble x to get y  
        xor_scrambler = np.array(np.random.binomial(1, self.bias, x[0].shape))
        
        # Create a mask that will set entire batches of the xor_scrambler to zero. The batches that are zero
        # will force the xor to return the original x for that batch
        scrambler_mask = np.array(np.random.binomial(1, self.bias, (self.batch_size,seq_length)))
        xor_scrambler = np.array(xor_scrambler *scrambler_mask[:, :, np.newaxis])

        aux_seq = np.array(np.logical_xor(x[0], xor_scrambler))

        #if the xor scambler is all zeros then x and y will be the same so target will be true
        actual_target = np.array(np.any(xor_scrambler, axis= 2, keepdims=True))
        #actual_target = actual_target[:, np.newaxis,np.newaxis]


        # create the target
        seq_length_tdummies = seq_length+2
        dummies_target = np.zeros([self.batch_size, seq_length_tdummies, 1], dtype=np.float32)
        target = np.concatenate((dummies_target, actual_target), axis=1)

        # data of x and dummies
        xx = [ self.augment(seq, markers, ctrl_start=ctrl_start, add_marker_data=True, add_marker_dummy = False) for seq in x ]

        # data of x
        data_1 = [arr for a in xx for arr in a[:-1]]

        # this is a marker between sub sequence x and dummies
        inter_seq = [self.add_ctrl(np.zeros((self.batch_size, 1, self.data_bits)), ctrl_inter, pos)]
                # Second Sequence for comparison
        
        markers2 = ctrl_output, ctrl_dummy, pos
        yy = [ self.augment(aux_seq, markers2, ctrl_start=ctrl_output, add_marker_data=False, add_marker_dummy = False)]
        data_2 = [arr for a in yy for arr in a[:-1]]

        #ctrl_data_select = [1,0]
        #aux_seq_wctrls=add_ctrl(aux_seq, ctrl_data_select, pos)
        #aux_seq_wctrls[:,-1,0:self.control_bits]=np.ones(len(ctrl_dummy))
        #data_2 = [aux_seq_wctrls]
      

        recall_seq = [self.add_ctrl(np.zeros((self.batch_size, 1, self.data_bits)), ctrl_dummy, pos)]
        dummy_data = [self.add_ctrl(np.zeros((self.batch_size, 1, self.data_bits)), np.ones(len(ctrl_dummy)), pos)]

 
        
        #print(data_1[0].shape)
        #print(inter_seq[0].shape)
        #print(data_2[0].shape)
        # concatenate all parts of the inputs
        inputs = np.concatenate(data_1 + inter_seq + data_2, axis=1)
     
        # PyTorch variables
        inputs = torch.from_numpy(inputs).type(self.dtype)
        target = torch.from_numpy(target).type(self.dtype)
        # TODO: batch might have different sequence lengths
        mask_all = inputs[..., 0:self.control_bits] == 1
        mask = mask_all[..., 0]
        for i in range(self.control_bits):
            mask = mask_all[..., i] * mask
        
        # TODO: fix the batch indexing
        # rest channel values of data dummies
        inputs[:, mask[0], 0:self.control_bits] = torch.tensor(ctrl_dummy).type(self.dtype)

        # Return data tuple.
        data_tuple = DataTuple(inputs, target)
        # Returning maximum length of sequence a - for now.
        aux_tuple = AlgSeqAuxTuple(mask, seq_length, 1)
        
        return data_tuple, aux_tuple
        
    # method for changing the maximum length, used mainly during curriculum learning
    def set_max_length(self, max_length):
        self.max_sequence_length = max_length


if __name__ == "__main__":
    """ Tests sequence generator - generates and displays a random sample"""

    # "Loaded parameters".
    params = {'control_bits': 3, 'data_bits': 8, 'batch_size': 1,
              'min_sequence_length': 10, 'max_sequence_length': 20, 
              'bias': 0.5 }
    # Create problem object.
    problem = SequenceComparisonCommandLines(params)
    # Get generator
    generator = problem.return_generator()
    # Get batch.
    data_tuple, aux_tuple = next(generator)

    # Display single sample (0) from batch.
    problem.show_sample(data_tuple, aux_tuple)
