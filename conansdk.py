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
        self.raw_adjacent_matrix = None
        '''
        self.conan_adjacent_table = {}
        self.conan_adjacent_matrix = numpy.zeros( (len(sdk),len(sdk)), dtype=numpy.int8 )
        '''
        self.real_sdk = set([])
        self.sorted_real_sdk = None

    def evaluateBuildSequence(self, workspace):
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
                    print(self.raw_adjacent_table)
                    print(self.raw_adjacent_matrix)
                    print(self.sorted_real_sdk)
                    return self.solveBuildSequence()
                except pp.ParseException as e:
                    tools.out.info('No match: %s'%(str(e)))

    def solveBuildSequence(self):
        sequence = []
        sequence.append(self.findSdkLeaves())
        print(sequence)
    
    def findSdkLeaves(self):
        leaves = set([])
        for i in range(len(self.sorted_real_sdk)):
            if numpy.sum(self.raw_adjacent_matrix[i,:]) == 0:
                leaves.add(self.sorted_real_sdk[i])
        return leaves

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
        real_sdk_index = {}
        self.sorted_real_sdk = sorted(self.real_sdk)
        for l in self.sorted_real_sdk:
            real_sdk_index.update({l:self.sorted_real_sdk.index(l)})

        self.raw_adjacent_matrix = numpy.zeros( (len(self.sorted_real_sdk),len(self.sorted_real_sdk)), dtype=numpy.int8 )
        for k, v in self.raw_adjacent_table.items():
            for l in v:
                self.raw_adjacent_matrix[real_sdk_index[k], real_sdk_index[l]] = 1

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

    def updateRealSdk(self, package):
        if package not in self.real_sdk:
            self.real_sdk.add(package)

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
    sdk.evaluateBuildSequence('E:\\workspace')