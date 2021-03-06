"""
File Name:          shard_module.py
Project:            bioseq-learning

File Description:

"""
import logging
from typing import List, Sequence, Tuple, Union

import torch
import torch.nn as nn
from torch import Tensor, device
from torchgpipe import GPipe
from torchgpipe.balance.blockpartition import solve
from src.utilities.profile_sequential_module import \
    profile_sequential_module


_LOGGER = logging.getLogger(__name__)


def shard_module(
        module: nn.Sequential,
        input_sample: Union[Tensor, Sequence[Tensor]],
        devices: Sequence[device],
        num_chunks: int,
        using_min_num_gpus: bool = True,
) -> Tuple[Union[GPipe, nn.Sequential], List[device]]:
    """shard a sequential module based on the memory usage of the components,
    profiled with the input sample from the argument, to a list of GPUs,
    that are assumed to have the same memory capacity.

    :param module: PyTorch sequential module
    :type module: nn.Sequential
    :param input_sample: batched input sample of one or more tensors used to
    profile the memory usage of each components in the sequential module
    :type input_sample: Union[Tensor, Sequence[Tensor]]
    :param devices: a list of PyTorch devices available
    :type devices: Sequence[device]
    :param num_chunks: number of chunks for GPipe sharded module; more
    chunks = better GPU utilization - more parallelization overhead
    :type num_chunks: int
    :param using_min_num_gpus: option for using minimum number of GPUs; if
    set to True, the function will select only the first few GPUs that are
    necessary for the whole module, instead of using all of the GPUs
    :type using_min_num_gpus: bool
    :return: a tuple made of a module and the list of used GPUs; if the
    module is sharded into a GPipe module, then the list would contain at
    least 2 GPUs; otherwise the module will be imported to the only
    computation device (GPUs or CPU) and returned
    :rtype: Tuple[Union[GPipe, nn.Sequential], List[device]]
    """

    # if more than 1 devices is necessary for the run ...
    # gpipe model on 1 gpu is much slower compared to ordinary model
    if len(devices) > 1:

        # get the sizes by layer in the sequential model
        # merely an rough estimation with a forward batch without optimizer
        _module_layer_sizes_in_byte: List[int] = profile_sequential_module(
            module=module,
            input=input_sample,
            chunks=1,
            param_scale=5.0,
            device=devices[0],
        )

        # scale the sizes by 2 (forward and backward) to play it safe
        _module_layer_sizes_in_byte = \
            [__m * 2 for __m in _module_layer_sizes_in_byte]

        # get the minimal necessary number of devices
        _num_devices: int = 0
        _module_size_in_byte: int = sum(_module_layer_sizes_in_byte)
        _gpu_sizes_in_byte: List[int] = [
            torch.cuda.get_device_properties(__d).total_memory
            for __d in devices
        ]

        for __n in range(1, len(devices) + 1):
            if sum(_gpu_sizes_in_byte[:__n]) > _module_size_in_byte:
                _num_devices = __n
                break

        if _num_devices == 0:
            _warning_msg = \
                f'PyTorch module with the estimated size of ' \
                f'{_module_size_in_byte / (1024**3):.1f} Gb exceeds the ' \
                f'combined memory capacity of all computation devices ' \
                f'({devices}). Proceeding with caution ...'
            _LOGGER.warning(_warning_msg)
        elif _num_devices < len(devices) and using_min_num_gpus:
            _warning_msg = \
                f'Using only {_num_devices} device(s) (' \
                f'{devices[:_num_devices]}) out of {len(devices)} ' \
                f'for the current trial.'
            _LOGGER.warning(_warning_msg)
            devices = devices[:_num_devices]
        else:
            # using all the available devices ...
            pass

        # cast the model to gpipe if necessary (too big for a single GPU)
        if len(devices) > 1:
            _balance = [len(__b) for __b in solve(
                _module_layer_sizes_in_byte,
                partitions=len(devices),
            )]
            # since we are not actually chunking the batches ...
            module = GPipe(
                module=module,
                balance=_balance,
                devices=devices,
                chunks=num_chunks,  # subject to change
                checkpoint='never',
            )
        else:
            # if the model can fit into a single GPU
            module = module.to(devices[0])
    else:
        # if the number of available devices is 1
        module = module.to(devices[0])

    return module, devices