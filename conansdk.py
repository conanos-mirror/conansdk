#-*- coding: utf-8 -*-
# module conansdk.py

__doc__ = \
"""
conansdk module - Classes and methods to construct adjacent table and adjacent matrix, based on which 
the build sequence of libraries contained in sdk can be evaluated.
"""

__version__ = "0.0.1"
__versionTime__ = "22 Jan 2019 15:04 UTC"
__author__ = "cppbitman <daihongjun@kedacom.com>"

#--------------------------------------------------------------------------------------------
#Construct the adjacent table and the adjacent matrix for sdk
#--------------------------------------------------------------------------------------------
import pyparsing as pp
import os
import numpy
from conans import tools

class ConanRecipeNotExist(Exception):
    def __init__(self, sdk, lib):
        self.sdk = sdk
        self.lib = lib

class GraphDotNotExist(Exception):
    def __init__(self, sdk, lib):
        self.sdk = sdk
        self.lib = lib

class RawPackage(object):
    def __init__(self, name, version):
        self.name = name
        self.version = version

    def __str__(self):
        return str(self.__class__) + str(self.__dict__)

    def __repr__(self):
        return self.name + "/" + self.version

    def __hash__(self):
        return hash(repr(self))
    
    def __eq__(self, other):
        if isinstance(other, RawPackage):  
            return ((self.name == other.name) and (self.version == other.version))
        return False

    def __lt__(self, other):
        assert(isinstance(other, RawPackage))
        return ((self.name < other.name) or ((self.name==other.name) and self.version < other.version))

'''
class ConanPackage(object):
    def __init__(self, name, version, user, channel):
        self.name = name
        self.version = version
        self.user = user
        self.channel = channel
'''

class ConanSdk(object):
    def __init__(self, name, sdk):
        self.name = name
        self.sdk = sdk
        self.raw_adjacent_table = {}
        self.raw_reverse_adjacent_table = {}
        self.raw_adjacent_matrix = None
        self.raw_adjacent_matrix_constructed = False
        '''
        self.conan_adjacent_table = {}
        self.conan_adjacent_matrix = numpy.zeros( (len(sdk),len(sdk)), dtype=numpy.int8 )
        '''
        self.real_sdk = set([])
        self.sorted_real_sdk = None
        self.sorted_real_sdk_index = {}

    def evaluateBuildSequenceAll(self, workspace):
        
        self.evaluateAdjacentMatrix(workspace)
        '''
        print(self.raw_adjacent_table)
        print(self.raw_reverse_adjacent_table)
        print(self.raw_adjacent_matrix)
        print(self.sorted_real_sdk)
        '''
        
        return self.solveBuildSequence()

    def evaluateBuildSequence(self, changing_library, workspace):
        self.evaluateAdjacentMatrix(workspace)
        return self.solveSubBuildSequence(changing_library)

    def solveSubBuildSequence(self, changing_library):
        build_sequence = []
        build_sequence.append(set([self.findPackageWithVersion(changing_library)]))
        continue_loop = True
        while continue_loop:
            next_radjacent = self.findNextReverseAdjacent(build_sequence[-1])
            if not next_radjacent:
                continue_loop = False
                continue
            for i in range(len(build_sequence)):
                for v in next_radjacent:
                    if v in build_sequence[i]:
                        build_sequence[i].remove(v)
            build_sequence.append(set(next_radjacent))
        return build_sequence

    def findPackageWithVersion(self, package_name):
        for v in self.sorted_real_sdk:
            if v.name == package_name:
                return v
        return None

    def findNextReverseAdjacent(self, current):
        next = []
        for v in current:
            if v in self.raw_reverse_adjacent_table:
                next.extend(list(self.raw_reverse_adjacent_table.get(v)))
        return next

    def evaluateAdjacentMatrix(self, workspace):
        if self.raw_adjacent_matrix_constructed:
            return
        for l in self.sdk:
            with tools.chdir(os.path.join(workspace, l)):
                if not os.path.exists('conanfile.py'):
                    raise ConanRecipeNotExist(self.name, l)
                dotfile = l+'.dot'
                os.system('conan info . --graph=%s'%(dotfile))
                if not os.path.exists(dotfile):
                    raise GraphDotNotExist(self.name, l)
                try:
                    result = self.defineGraphPattern().parseFile(dotfile, parseAll=True)
                    self.recordAdjacents(result['adjacents'])
                except pp.ParseException as e:
                    tools.out.info('No match: %s'%(str(e)))
        self.raw_adjacent_matrix_constructed=True

    def solveBuildSequence(self):
        build_sequence = []
        (leaves, rest_outdegree) = self.findSdkLeaves()
        build_sequence.append(leaves)
        while rest_outdegree:
            next_layer = {}
            for k, v in rest_outdegree.items():
                built_outdegree=self.evaluateBuiltOutdegree(k, build_sequence)
                if built_outdegree > 0 and (v - built_outdegree)<=0:
                    next_layer.update({k:self.sorted_real_sdk[k]})
            if next_layer:
                build_sequence.append(set(next_layer.values()))
                for i in next_layer.keys():
                    rest_outdegree.pop(i)
        #print(build_sequence)
        return build_sequence

    def evaluateBuiltOutdegree(self,index, build_sequence):
        outdegree_sum = 0
        for layer in build_sequence:
            for l in layer:
                outdegree_sum += self.raw_adjacent_matrix[index, self.sorted_real_sdk_index[l]]
        return outdegree_sum

    def findSdkLeaves(self):
        leaves = set([])
        rest_outdegree = {}
        for i in range(len(self.sorted_real_sdk)):
            result = numpy.sum(self.raw_adjacent_matrix[i,:])
            if result == 0:
                leaves.add(self.sorted_real_sdk[i])
            else:
                rest_outdegree.update({i:result})
        return (leaves,rest_outdegree)

    def recordAdjacents(self, adjacents):
        while len(adjacents):
            lhs = adjacents.pop(0)
            adjacents.pop(0)
            adjacents.pop(0)
            rhs = adjacents.pop(0)
            adjacents.pop(0)
            self.addAdjacent(lhs, rhs)
        self.updateAdjacentMatrix()

    def updateAdjacentMatrix(self):
        self.sorted_real_sdk = sorted(self.real_sdk)
        for l in self.sorted_real_sdk:
            self.sorted_real_sdk_index.update({l:self.sorted_real_sdk.index(l)})

        self.raw_adjacent_matrix = numpy.zeros( (len(self.sorted_real_sdk),len(self.sorted_real_sdk)), dtype=numpy.int8 )
        for k, v in self.raw_adjacent_table.items():
            for l in v:
                self.raw_adjacent_matrix[self.sorted_real_sdk_index[k], self.sorted_real_sdk_index[l]] = 1

    def addAdjacent(self, lhs, rhs):
        result = self.definePackagePattern().parseString(lhs, parseAll=True)
        package = RawPackage(result['name'].strip(), result['version'].strip())
        self.updateRealSdk(package)
        if package not in self.raw_adjacent_table:
            self.raw_adjacent_table.update({package:set([])})
        for p in rhs:
            result = self.definePackagePattern().parseString(p, parseAll=True)
            rhs_package = RawPackage(result['name'].strip(), result['version'].strip())
            self.updateRealSdk(rhs_package)
            self.raw_adjacent_table.get(package).add(rhs_package)

            self.updateReverseAdjacentTable(package, rhs_package)

    def updateRealSdk(self, package):
        if package not in self.real_sdk:
            self.real_sdk.add(package)

    def updateReverseAdjacentTable(self, lhs_package, rhs_package):
        if rhs_package not in self.raw_reverse_adjacent_table:
            self.raw_reverse_adjacent_table.update({rhs_package:set([])})
        self.raw_reverse_adjacent_table.get(rhs_package).add(lhs_package)


    def definePackagePattern(self):
        first = pp.Word(pp.alphas+"_", exact=1)
        rest = pp.Word(pp.alphanums+"_")
        identifier = first+pp.Optional(rest)

        digit = pp.Word(pp.nums, exact=1)
        nonzero_digit = pp.Word(pp.nums, exact=1, excludeChars=['0'])
        nonnegative_digits = pp.Or([digit, nonzero_digit+pp.Word(pp.nums)])

        user = channel = identifier
        letterdigit = pp.Word(pp.alphanums, exact=1)

        library = pp.Combine(letterdigit + pp.Word(pp.alphanums+"-"+"_"))
        rc = pp.Combine(pp.Literal('-rc')+'-'+nonnegative_digits)
        alpha = pp.Combine(pp.Literal('-alpha')+'-'+nonnegative_digits)
        beta = pp.Combine(pp.Literal('-beta')+'-'+nonnegative_digits)
        version = pp.Combine(nonnegative_digits+'.'+nonnegative_digits+ pp.Optional('.'+nonnegative_digits)+
                  pp.Optional('.'+nonnegative_digits)+pp.Optional(pp.Or([rc, alpha, beta])))
        user_channel = pp.Or([user+'/'+channel, pp.Literal('PROJECT')])
        package = pp.Combine(library.setResultsName('name')+'/'+version.setResultsName('version')+'@'+ user_channel)
        quote_package = pp.Combine('"'+package+'"')
        return quote_package

    def defineGraphPattern(self):
        quote_package = self.definePackagePattern()
        quote_package_list = pp.OneOrMore(quote_package)
        dependant = pp.Literal('{') + pp.Group(quote_package_list) + pp.Literal('}')
        adjacent = quote_package + pp.Literal('->') + dependant
        graph = pp.Literal('digraph') + pp.Literal('{') + pp.Group(pp.OneOrMore(adjacent)).setResultsName('adjacents') + pp.Literal('}')
        return graph

if __name__ == '__main__':
    sdk = ConanSdk('gstreamer',['gstreamer'])
    print(sdk.evaluateBuildSequenceAll('E:\\workspace'))
    print(sdk.evaluateBuildSequence('zlib', 'E:\\workspace'))