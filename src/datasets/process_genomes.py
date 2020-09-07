"""
File Name:          process_genomes.py
Project:            bioseq-learning-cd

File Description:

"""
import os
import json

from typing import Optional, Iterator, List

import pandas as pd
from Bio import SeqIO, SeqRecord
from joblib import Parallel, delayed, parallel_backend

from src.utilities import create_directory
from src.datasets import conserved_domain_search


def process_genome(
        genome_dir_path: str,
        genome_id: Optional[str] = None,
):
    """process a PATRIC genome

    the processing steps are listed as the following:
    - prepare the directories
    - split all the contigs and their features
    - search for conserved domains on all the contigs
    - create an info file

    :param genome_dir_path: path to PATRIC genome directory
    :type genome_dir_path: str
    :param genome_id: optional ID for genome ID; using the genome
    directory name if not given
    :type genome_id: str
    :return: None
    """

    # get the genome ID if not given
    genome_dir_path: str = os.path.join(genome_dir_path, '')
    genome_id: str = genome_id if genome_id else \
        os.path.basename(genome_dir_path[:-1])

    # get the genome and feature paths
    contig_seq_path: str = os.path.join(genome_dir_path, f'{genome_id}.fna')
    feature_path: str = \
        os.path.join(genome_dir_path,  f'{genome_id}.PATRIC.features.tab')

    # create the subdirectories if not exist
    # - ./contigs: contig nucleotide sequences
    # - ./features:  feature annotations for every contig
    # - ./conserved_domains: conserved domain results for every contig
    contig_dir_path: str = os.path.join(genome_dir_path, 'contigs')
    feature_dir_path: str = os.path.join(genome_dir_path, 'features')
    conserved_domain_dir_path: str = \
        os.path.join(genome_dir_path, 'conserved_domains')
    create_directory(contig_dir_path)
    create_directory(feature_dir_path)
    create_directory(conserved_domain_dir_path)

    # read the entire genome into list of contig sequences
    contig_seq_record_iter: Iterator[SeqRecord] = \
        SeqIO.parse(contig_seq_path, 'fasta')

    # split genome contigs and write into files named with their PATRIC IDs
    contig_info_dict: dict = {}
    _contig_seq_record: SeqRecord
    for _contig_seq_record in contig_seq_record_iter:
        _contig_id: str = _contig_seq_record.id
        _contig_seq_path: str = \
            os.path.join(contig_dir_path, f'{_contig_id}.fna')
        contig_info_dict[_contig_id] = {
            'length': len(_contig_seq_record),
        }
        with open(_contig_seq_path, 'w+') as _f:
            SeqIO.write(_contig_seq_record, _f, 'fasta')

    # split PATRIC features and write into files named with their PATRIC IDs
    # assume that accession is the same as contig in PATRIC
    feature_df = pd.read_table(feature_path)
    _accession: str
    _feature_by_accession_df: pd.DataFrame
    for _accession, _feature_by_accession_df \
            in feature_df.groupby('accession'):
        _feature_by_accession_path: str = \
            os.path.join(feature_dir_path, f'{_accession}.tsv')
        _source_mask = (_feature_by_accession_df['feature_type'] == 'source')
        _feature_by_accession_df[~_source_mask].to_csv(
            _feature_by_accession_path, index=None, sep='\t')

    # iterate through all the contigs again for conserved domain search
    for _contig_id in contig_info_dict.keys():
        _contig_seq_path: str = \
            os.path.join(contig_dir_path, f'{_contig_id}.fna')
        _contig_cd_xml_path: str = \
            os.path.join(conserved_domain_dir_path, f'{_contig_id}.xml')
        conserved_domain_search(
            nucleotide_seq_path=_contig_seq_path,
            cd_xml_path=_contig_cd_xml_path,
        )

    # save the genome information in json format
    genome_info_path: str = os.path.join(genome_dir_path, 'info.json')
    genome_info: dict = {
        'genome_name': feature_df['genome_name'].unique()[0],
        'number_of_contigs': len(contig_info_dict),
        'contigs': contig_info_dict,
    }
    with open(genome_info_path, 'w+') as _fh:
        json.dump(genome_info, _fh, indent=4)


def process_genomes(
        genome_parent_dir_path: str,
        num_threads: int = 1,
):
    """process PATRIC genomes in the given parent directory in parallel

    :param genome_parent_dir_path: path to the parent directory of all
    the PATRIC genome directories to be processed
    :type genome_parent_dir_path: str
    :param num_threads: maximum number of threads for parallelization
    :type num_threads: int
    :return: None
    """

    # clamp the number of processes between range [1, number of CPU cores]
    num_threads: int = max(1, min(num_threads, os.cpu_count()))

    # get all the paths to genomes
    genome_paths: List[str] = [
        os.path.join(genome_parent_dir_path, _d)
        for _d in os.listdir(genome_parent_dir_path)
        if os.path.isdir(os.path.join(genome_parent_dir_path, _d))
    ]

    # embarrassingly process the genome processing functions with joblib
    with parallel_backend('threading', n_jobs=num_threads):
        Parallel()(delayed(process_genome)(_p) for _p in genome_paths)
