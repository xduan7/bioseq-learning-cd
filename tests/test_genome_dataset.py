"""
File Name:          test_masked_genome_dataset.py
Project:            bioseq-learning

File Description:

"""
import os
import unittest
from typing import List

from torch.utils.data import DataLoader

from src.datasets import GenomeDataset, GenomeIterDataset
from src.datasets.genome_dataset import \
    PADDING_CHAR, NUCLEOTIDE_CHAR_INDEX_DICT


_TEST_EXAMPLES_DIR_PATH: str = \
    os.path.join(os.path.dirname(os.path.realpath(__file__)), 'examples')
_TEST_GENOME_DIR_PATHS: List[str] = [
    os.path.join(
        _TEST_EXAMPLES_DIR_PATH,
        'genome_processing_results_reference',
        '562.2283'
    )]
_TEST_SEQ_LEN: int = 100
_TEST_NUM_MASKS: int = 5
_TEST_MAX_NUM_PADDINGS: int = 10
_TEST_BATCH_SIZE: int = 16
_PADDING_INDEX: int = NUCLEOTIDE_CHAR_INDEX_DICT[PADDING_CHAR]


class TestGenomeDataset(unittest.TestCase):
    """unittest class for 'genome_dataset' and 'genome_iter_dataset' classes
    """
    def test_genome_dataset(self):
        """test 'genome_dataset' class
        """
        genome_dataset = GenomeDataset(
            genome_dir_paths=_TEST_GENOME_DIR_PATHS,
            seq_len=_TEST_SEQ_LEN,
            max_num_paddings=_TEST_MAX_NUM_PADDINGS,
        )

        for _i in range(len(genome_dataset)):
            _indexed_seq, _padding_mask = genome_dataset[_i]
            # test if all the indexed values are in the index dict
            assert set([_v.item() for _v in _indexed_seq.unique()]).issubset(
                set(NUCLEOTIDE_CHAR_INDEX_DICT.values()))
            # test if the number of paddings is valid (no bigger)
            assert _padding_mask.sum().item() <= _TEST_MAX_NUM_PADDINGS

    def test_genome_iter_dataset(self):
        """test 'genome_iter_dataset' class
        """
        genome_iter_dataloader = DataLoader(
            GenomeIterDataset(
                genome_dir_paths=_TEST_GENOME_DIR_PATHS,
                seq_len=_TEST_SEQ_LEN,
                max_num_paddings=_TEST_MAX_NUM_PADDINGS,
            ),
            batch_size=_TEST_BATCH_SIZE,
        )

        for _batch_data in genome_iter_dataloader:
            assert _batch_data[0].shape == (_TEST_BATCH_SIZE, _TEST_SEQ_LEN)
            assert _batch_data[1].shape == (_TEST_BATCH_SIZE, _TEST_SEQ_LEN)
            break


if __name__ == '__main__':
    unittest.main()