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


class ConanSdk(object):
    def __init__(self, name, sdk):
        self.name = name
        self.sdk = sdk
        self.adjacent_table = {}
        self.adjacent_matrix = numpy.zeros( (len(sdk),len(sdk)), dtype=numpy.int8 )

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
                    adjacents = result['adjacents']
                    #print(adjacents)
                    left = right = None
                    while len(adjacents):
                        left = adjacents.pop(0)
                        adjacents.pop(0)
                        adjacents.pop(0)
                        right = adjacents.pop(0)
                        adjacents.pop(0)
                        self.addToAdjacentObject(left, right)
                except pp.ParseException as e:
                    tools.out.info('No match: %s'%(str(e)))
    
    def addToAdjacentObject(self, left, right):
        print(left, '->', right)

    def defineGraphPattern(self):
        first = pp.Word(pp.alphas+"_", exact=1)
        rest = pp.Word(pp.alphanums+"_")
        identifier = first+pp.Optional(rest)

        digit = pp.Word(pp.nums, exact=1)
        nonzero_digit = pp.Word(pp.nums, exact=1, excludeChars=['0'])
        nonnegative_digits = pp.Or([digit, nonzero_digit+pp.Word(pp.nums)])

        user = channel = identifier
        letterdigit = pp.Word(pp.alphanums, exact=1)

        library = letterdigit + pp.Word(pp.alphanums+"-"+"_")
        rc = pp.Combine(pp.Literal('-rc')+'-'+nonnegative_digits)
        alpha = pp.Combine(pp.Literal('-alpha')+'-'+nonnegative_digits)
        beta = pp.Combine(pp.Literal('-beta')+'-'+nonnegative_digits)
        version = pp.Combine(nonnegative_digits+'.'+nonnegative_digits+ pp.Optional('.'+nonnegative_digits)+
                  pp.Optional('.'+nonnegative_digits)+pp.Optional(pp.Or([rc, alpha, beta])))
        user_channel = pp.Or([user+'/'+channel, pp.Literal('PROJECT')])
        package = pp.Combine(library+'/'+version+'@'+ user_channel)
        quote_package = pp.Combine('"'+package+'"')
        quote_package_list = pp.OneOrMore(quote_package)
        dependant = pp.Literal('{') + pp.Group(quote_package_list) + pp.Literal('}')
        adjacent = quote_package + pp.Literal('->') + dependant
        graph = pp.Literal('digraph') + pp.Literal('{') + pp.Group(pp.OneOrMore(adjacent)).setResultsName('adjacents') + pp.Literal('}')
        return graph

if __name__ == '__main__':
    sdk = ConanSdk('gstreamer',['gstreamer'])
    sdk.evaluateBuildSequence('E:\\workspace')