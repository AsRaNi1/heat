import itertools
import torch

from .communication import MPI, MPI_WORLD
from . import dndarray
from . import factories
from . import operations

__all__ = [
    'matmul',
    'transpose',
    'tril',
    'triu'
]


def matmul(a, b, out=None, out_split=None):
    """
    Matrix multiplication function based of the CRMM method as described in Reference 1. Communication scheme based upon reference [2]

    for comment context -> a @ b = c

    Parameters
    ----------
    a : ht.tensor
        2 dimensions: L x P

    b : ht.tensor
        2 dimensions: P x Q

    out : ht.tensor
        Optional
        output tensor

    out_split : int
        Optional
        split direction of the output tensor if out is None
        if out is None and out_split is None then the split direction of a is chosen

    Returns
    -------
    ht.tensor
        returns a tensor with the result of a @ b
        the

    References
    ----------
    [1] R. Gu, et al., "Improving Execution Concurrency of Large-scale Matrix Multiplication on Distributed Data-parallel Platforms,"
        IEEE Transactions on Parallel and Distributed Systems, vol 28, no. 9. 2017.
    [2] S. Ryu and D. Kim, "Parallel Huge Matrix Multiplication on a Cluster with GPGPU Accelerators,"
        2018 IEEE International Parallel and Distributed Processing Symposium Workshops (IPDPSW), Vancouver, BC, 2018, pp. 877-882.

    Process:
    --------
    1. split a and b into blocks of the respective sizes (M x kB and kB x N)
        kB must be the same in both
        if a common kB cannot be found then x rows/columns can be sliced off and saved for later
            this cut must occur in the 'P' dimension of both matricies
            best way to do this is to either equate all of the

    detailed process:
    -----------------
    1. get the lshape of the data on all procs

    possible problems:
    -> a and b not the same splits
    """
    if a.gshape[-1] != b.gshape[-2]:
        raise ValueError("If the last dimension of a ({}) is not the same size as the second-to-last dimension of b. ({})".format(a.gshape[-1], b.gshape[-2]))

    if not a.is_distributed() and not b.is_distributed():  # else its simple matmul from torch
        # todo: make this actually work in the proper form....needs to return a DNDarray
        return torch.matmul(a._DNDarray__array, b._DNDarray__array)
    else:
        # block sizes dont need to be the same. thy just need the same inner dimmension (kB)
        kB = 0
        rem_a, rem_b = [0] * 2
        if a.split == len(a.gshape)-1 and b.split == len(a.gshape)-2:  # if the split direction is the last dim in a and the first dim in b
            # the max inner dim (kB) is the min value from the result of the integer division of the last dim of a/world size and the first dim of b/world size
            kB = min([a.gshape[-1] // a.comm.size, b.gshape[0] // b.comm.size])
        elif a.split == len(a.gshape)-1:
            kB = a.gshape[-1] // a.comm.size
        elif b.split == len(a.gshape)-2:
            kB = b.gshape[-2] // b.comm.size
            kB = kB if kB < a.gshape[-1] else a.gshape[-1]
        else:  # if the split is not in either of these directions then kB can be anything, it just needs to be tuned
            # what to do here?
            raise NotImplementedError("need to implement case of split 0 and split 1 for a and b respectively")
            pass
        # kB = int(kB)
        if a.lshape[-1] % kB != 0:
            rem_a = 1
        if b.lshape[-2] % kB != 0:
            rem_b = 1

        # print(kB, rem_a, rem_b)

        # get the lshape map to determine what needs to be sent where as well as M and N
        # lshape map dims -> {node, a=0, b=1, lshape}
        lshape_map = factories.zeros((a.comm.size, 2, len(a.gshape)), dtype=int)
        lshape_map[a.comm.rank, 0, :] = torch.Tensor(a.lshape)
        lshape_map[b.comm.rank, 1, :] = torch.Tensor(b.lshape)
        a.comm.Allreduce(MPI.IN_PLACE, lshape_map, MPI.SUM)
        # print(lshape_map)

        # find mB (first blocking dim for a) and nB (2nd blocking dim for b)
        mB = lshape_map[:, 0, -2].min().item()
        nB = lshape_map[:, 1, -1].min().item()

        # todo: make nB smaller to allow for nonblocking communication to work while some communication is happening
        nB = int(nB // 2)
        mB = int(mB)
        # todo: handle the outside dimensional remainders
        print('mb', mB, 'kB', kB, 'nb', nB)

        # check for remaining dims in the outside dimensions
        rem_a_out, rem_b_out = 0, 0
        if a.lshape[-2] % mB != 0:
            rem_a_out = 1
        if b.lshape[-1] % nB != 0:
            rem_b_out = 1
        # print('rems:', rem_a_out, rem_a, rem_b, rem_b_out)
        # print('block sizes:', '\n a:', mB, kB, '\n b:', kB, nB)
        # if there is any rem_a then there are remainders on all processes

        # get the flags from all processes
        # rem_map dims guide -> {process number, a/b (0/1), True/False (1/0) if there is a remainder in this dimension
        rem_map = factories.zeros((a.comm.size, 2, 2))
        rem_map[a.comm.rank, 0, :] = (rem_a_out, rem_a)
        rem_map[a.comm.rank, 1, :] = (rem_b, rem_b_out)
        a.comm.Allreduce(MPI.IN_PLACE, rem_map, MPI.SUM)
        # print(rem_map)
        # TODO: deal with the remainders...joy

        # index_map dims guide -> {process number, a=0/b=1, relevent 1st index, 2nd index}
        index_map = factories.zeros((a.comm.size, 2, 2, 2), dtype=int)
        a_idx = a.comm.chunk(a.shape, a.split)[2]
        index_map[a.comm.rank, 0, 0] = (a_idx[0].start, a_idx[0].stop)
        index_map[a.comm.rank, 0, 1] = (a_idx[1].start, a_idx[1].stop)
        b_idx = b.comm.chunk(b.shape, b.split)[2]
        index_map[b.comm.rank, 1, 0] = (b_idx[0].start, b_idx[0].stop)
        index_map[b.comm.rank, 1, 1] = (b_idx[1].start, b_idx[1].stop)
        a.comm.Allreduce(MPI.IN_PLACE, index_map, MPI.SUM)
        # print(index_map)

        # with the index map then the communication can be determined
        # this index map will also be used as a meta data / dictionary when the data is passed around

        # Index map is done, remainder map is done,
        # todo: determine communication scheme
        # for the communication scheme, the output array needs to be created
        c_shape = (a.gshape[-2], b.gshape[-1])
        c = factories.zeros(c_shape, split=out_split if out_split is not None else a.split)

        # get the index map for c
        c_index_map = factories.zeros((c.comm.size, 2, 2))
        c_idx = c.comm.chunk(c.shape, c.split)[2]
        c_index_map[c.comm.rank, 0, :] = (c_idx[0].start, c_idx[0].stop)
        c_index_map[c.comm.rank, 1, :] = (c_idx[1].start, c_idx[1].stop)
        c.comm.Allreduce(MPI.IN_PLACE, c_index_map, MPI.SUM)

        # TODO: to determine which direction to shuffle the data. i.e. which requires the least communication

        # need to make the blocking a bit more intelligent,
        # the sizes are fine but the locations of them need to be chosen
        # the blocks are shifted in the 2nd dimension of A for as many remainders there are between the blocks in the first dim of B
        a_block_map = torch.zeros((a.comm.size, a.shape[-2] // mB // a.comm.size, a.shape[-1] // kB, 2))
        # units-> [process, dim0 block number, dim1 block number, start coord] **indices are local
        for pr in range(a.comm.size):
            start0 = index_map[pr, 0, 0, 0].item()
            stop0 = index_map[pr, 0, 0, 1].item()
            start1 = index_map[pr, 0, 1, 0].item()
            stop1 = index_map[pr, 0, 1, 1].item()
            # a_block_map[pr] = torch.zeros(((stop0 - start0) // mB, (stop1 - start1) // kB, 2))

            for dim0 in range((stop0 - start0) // mB):
                # loop over the number of blocks in the 0th dimension
                for dim1 in range((stop1 - start1) // kB):
                    # loop over the number of blocks in the 1st dimension
                    # todo: figure out how to change this for a_split=1
                    # todo: this doesnt work for multiple blocks in the 0th dim...
                    a_block_map[pr, dim0, dim1] = torch.tensor((dim0 * mB, dim1 * kB), dtype=torch.int)

        cnt = 0
        for r in rem_map[:, 1, 0]:
            if r.item():
                cnt += 1
                a_block_map[:, :, cnt, 1] += cnt

        b_block_map = torch.zeros((b.comm.size, b.shape[-2] // kB // b.comm.size, b.shape[-1] // nB, 2))
        # units-> [process, dim0 block number, dim1 block number, start coord] **indices are local
        for pr in range(b.comm.size):
            start0 = index_map[pr, 1, 0, 0].item()
            stop0 = index_map[pr, 1, 0, 1].item()
            start1 = index_map[pr, 1, 1, 0].item()
            stop1 = index_map[pr, 1, 1, 1].item()
            # b_block_map[pr] = torch.zeros(((stop0 - start0) // kB, (stop1 - start1) // nB, 2))

            for dim0 in range((stop0 - start0) // kB):
                # loop over the number of blocks in the 0th dimension
                for dim1 in range((stop1 - start1) // nB):
                    # loop over the number of blocks in the 1st dimension
                    # todo: figure this out for b_split=1
                    b_block_map[pr, dim0, dim1] = torch.tensor((dim0 * kB, dim1 * nB), dtype=torch.int)

            # TODO: need to fix this for the case that the blocks in 'b' need to be shifted (in a_split = 0 this isnt needed)
            # cnt = 0
            # for r in rem_map[:, 1, 0]:
            #     if r.item():
            #         cnt += 1
            #         b_block_map[pr][:, cnt, 1] += cnt

        # print(a_block_map[0, :])
        # print(b_block_map[:, :, 0])

        # now the block maps are done, next need to determine the passing order
        # c_00 = a_block_map[0, :]
        # if a.comm.rank == 0:
        #     a_start0 = int(a_block_map[0, 0, 1, 0].item())
        #     a_start1 = int(a_block_map[0, 0, 1, 1].item())
        #     a_block = a._DNDarray__array[a_start0:a_start0 + mB, a_start1:a_start1 + kB]
        #
        #     b_start0 = int(b_block_map[0, 0, 0, 0].item())
        #     b_start1 = int(b_block_map[0, 0, 0, 1].item())
        #     b_block = b._DNDarray__array[b_start0:b_start0 + kB, b_start1:b_start1 + nB]
        #     print(a_block @ b_block)
        ####################################################################

        print(a_block_map.shape, b_block_map.shape)
        # work loop: loop over all processes
        # ibcast from each node
        # Irecv from last loop
        # do calculation (if first loop use what is only on node)
        req = {}
        a_lp_data = {}
        for pr in range(a.comm.size):
            # ibcast data on node first
            if a.comm.rank == pr:
                a_lp_data[pr] = a._DNDarray__array
            else:
                a_lp_data[pr] = torch.empty((lshape_map[pr, 0, 0].item(), lshape_map[pr, 0, 1].item()))

            # sending a to all nodes for b to operate with
            req[pr] = a.comm.Ibcast(a_lp_data[pr], root=pr)

            # receie the data from the last loop
            if pr != 0:
                req[pr - 1].wait()
                # after receiving the last loop's bcast
            else:
                # in the first loop the data on node is used instead of what was casted
                # for the multiplication need to get the indices of the blocks for a and b
                # below needs to be looped over for the number of blocks in c
                # print(a_block_map[pr].shape)
                # todo: the looping is wrong here! need to zip the middle dims C_ij = sum(over k)(a_ik @ b_kj)
                proc0 = a.comm.rank
                for bl_0_b in range(b_block_map[proc0].shape[0]):
                    for bl_1_b in range(b_block_map[proc0].shape[1]):
                        for bl_0_a in range(a_block_map[proc0].shape[0]):  # todo: this loop needs to be the loop for k
                            for bl_1_a in range(a_block_map[proc0].shape[1]):  # loop over the number of blocks in a (dim0)
                                a_start1 = int(a_block_map[proc0, bl_0_a, bl_1_a, 1].item())
                                a_start0 = int(a_block_map[proc0, bl_0_a, bl_1_a, 0].item())
                                a_block = a._DNDarray__array[a_start0:a_start0 + mB, a_start1:a_start1 + kB]

                                b_start0 = int(b_block_map[proc0, bl_0_b, bl_1_b, 0].item())
                                b_start1 = int(b_block_map[proc0, bl_0_b, bl_1_b, 1].item())
                                b_block = b._DNDarray__array[b_start0:b_start0 + kB, b_start1:b_start1 + nB]

                                c_start0 = a_start0
                                c_start1 = b_start1
                                print(bl_0_a, bl_1_a, bl_0_b, bl_1_b, c_start0, c_start1)
                                # print(c.comm.rank, c_start0, c_start1, a_start1, b_start0, '\n', a_block @ b_block)
                                c._DNDarray__array[c_start0:c_start0 + mB, c_start1:c_start1 + nB] += a_block @ b_block

            # need to wait if its the last loop
            if pr == a.comm.size - 1:
                req[pr].wait()
        print(c)



########################################################################################################################################################


def transpose(a, axes=None):
    """
    Permute the dimensions of an array.

    Parameters
    ----------
    a : array_like
        Input array.
    axes : None or list of ints, optional
        By default, reverse the dimensions, otherwise permute the axes according to the values given.

    Returns
    -------
    p : ht.DNDarray
        a with its axes permuted.
    """
    # type check the input tensor
    if not isinstance(a, dndarray.DNDarray):
        raise TypeError('a must be of type ht.DNDarray, but was {}'.format(type(a)))

    # set default value for axes permutations
    dimensions = len(a.shape)
    if axes is None:
        axes = tuple(reversed(range(dimensions)))
    # if given, sanitize the input
    else:
        try:
            # convert to a list to allow index access
            axes = list(axes)
        except TypeError:
            raise ValueError('axes must be an iterable containing ints')

        if len(axes) != dimensions:
            raise ValueError('axes do not match tensor shape')
        for index, axis in enumerate(axes):
            if not isinstance(axis, int):
                raise TypeError('axis must be an integer, but was {}'.format(type(axis)))
            elif axis < 0:
                axes[index] = axis + dimensions

    # infer the new split axis, it is the position of the split axis within the new axes permutation
    try:
        transposed_split = axes.index(a.split) if a.split is not None else None
    except ValueError:
        raise ValueError('axes do not match tensor shape')

    # try to rearrange the tensor and return a new transposed variant
    try:
        transposed_data = a._DNDarray__array.permute(*axes)
        transposed_shape = tuple(a.shape[axis] for axis in axes)

        return dndarray.DNDarray(transposed_data, transposed_shape, a.dtype, transposed_split, a.device, a.comm)
    # if not possible re- raise any torch exception as ValueError
    except (RuntimeError, IndexError) as exception: 
        raise ValueError(str(exception))


# statically allocated index slices for non-iterable dimensions in triangular operations
__index_base = (slice(None), slice(None),)


def __tri_op(m, k, op):
    """
    Generic implementation of triangle operations on tensors. It takes care of input sanitation and non-standard
    broadcast behavior of the 2D triangle-operators.

    Parameters
    ----------
    m : ht.DNDarray
        Input tensor for which to compute the triangle operator.
    k : int, optional
        Diagonal above which to apply the triangle operator, k<0 is below and k>0 is above.
    op : callable
        Implementation of the triangle operator.

    Returns
    -------
    triangle_tensor : ht.DNDarray
        DNDarray with the applied triangle operation

    Raises
    ------
    TypeError
        If the input is not a tensor or the diagonal offset cannot be converted to an integral value.
    """
    if not isinstance(m, dndarray.DNDarray):
        raise TypeError('Expected m to be a tensor but was {}'.format(type(m)))

    try:
        k = int(k)
    except ValueError:
        raise TypeError('Expected k to be integral, but was {}'.format(type(k)))

    # chunk the global shape of the tensor to obtain the offset compared to the other ranks
    offset, _, _ = m.comm.chunk(m.shape, m.split)
    dimensions = len(m.shape)

    # manually repeat the input for vectors
    if dimensions == 1:
        triangle = m._DNDarray__array.expand(m.shape[0], -1)
        if torch.numel(triangle > 0):
            triangle = op(triangle, k - offset)

        return dndarray.DNDarray(
            triangle,
            (m.shape[0], m.shape[0],),
            m.dtype,
            None if m.split is None else 1,
            m.device,
            m.comm
        )

    original = m._DNDarray__array
    output = original.clone()

    # modify k to account for tensor splits
    if m.split is not None:
        if m.split + 1 == dimensions - 1:
            k += offset
        elif m.split == dimensions - 1:
            k -= offset

    # in case of two dimensions we can just forward the call to the callable
    if dimensions == 2:
        if torch.numel(original) > 0:
            op(original, k, out=output)
    # more than two dimensions: iterate over all but the last two to realize 2D broadcasting
    else:
        ranges = [range(elements) for elements in m.lshape[:-2]]
        for partial_index in itertools.product(*ranges):
            index = partial_index + __index_base
            op(original[index], k, out=output[index])

    return dndarray.DNDarray(output, m.shape, m.dtype, m.split, m.device, m.comm)


def tril(m, k=0):
    """
    Returns the lower triangular part of the tensor, the other elements of the result tensor are set to 0.

    The lower triangular part of the tensor is defined as the elements on and below the diagonal.

    The argument k controls which diagonal to consider. If k=0, all elements on and below the main diagonal are
    retained. A positive value includes just as many diagonals above the main diagonal, and similarly a negative
    value excludes just as many diagonals below the main diagonal.

    Parameters
    ----------
    m : ht.DNDarray
        Input tensor for which to compute the lower triangle.
    k : int, optional
        Diagonal above which to zero elements. k=0 (default) is the main diagonal, k<0 is below and k>0 is above.

    Returns
    -------
    lower_triangle : ht.DNDarray
        Lower triangle of the input tensor.
    """
    return __tri_op(m, k, torch.tril)


def triu(m, k=0):
    """
    Returns the upper triangular part of the tensor, the other elements of the result tensor are set to 0.

    The upper triangular part of the tensor is defined as the elements on and below the diagonal.

    The argument k controls which diagonal to consider. If k=0, all elements on and below the main diagonal are
    retained. A positive value includes just as many diagonals above the main diagonal, and similarly a negative
    value excludes just as many diagonals below the main diagonal.

    Parameters
    ----------
    m : ht.DNDarray
        Input tensor for which to compute the upper triangle.
    k : int, optional
        Diagonal above which to zero elements. k=0 (default) is the main diagonal, k<0 is below and k>0 is above.

    Returns
    -------
    upper_triangle : ht.DNDarray
        Upper triangle of the input tensor.
    """
    return __tri_op(m, k, torch.triu)
