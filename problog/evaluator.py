from __future__ import print_function

from .interface import ground
from .logic.program import LogicProgram
from .logic.formula import LogicFormula
from .logic.basic import Constant, Term
from .logic.eb_engine import computeFunction


from collections import defaultdict
import subprocess
import sys, os



class Semiring(object) :
    
    def one(self) :
        raise NotImplementedError()
    
    def zero(self) :
        raise NotImplementedError()
        
    def plus(self, a, b) :
        raise NotImplementedError()

    def times(self, a, b) :
        raise NotImplementedError()

    def negate(self, a) :
        raise NotImplementedError()

    def value(self, a) :
        raise NotImplementedError()

    def normalize(self, a, Z) :
        raise NotImplementedError()
    
class SemiringProbability(Semiring) :

    def one(self) :
        return 1.0

    def zero(self) :
        return 0.0
        
    def plus(self, a, b) :
        return a + b
        
    def times(self, a, b) :
        return a * b

    def negate(self, a) :
        return 1.0 - a
                
    def value(self, a) :
        if isinstance(a, Constant) :
            return a.value
        elif isinstance(a, Term) :
            return computeFunction(a.functor, a.args, None).value
        else :
            return a

    def normalize(self, a, Z) :
        return a/Z

class SemiringSymbolic(Semiring) :
    
    def one(self) :
        return "1"
    
    def zero(self) :
        return "0"
        
    def plus(self, a, b) :
        if a == "0" :
            return b
        elif b == "0" :
            return a
        else :
            return "(%s + %s)" % (a,b)

    def times(self, a, b) :
        if a == "0" or b == "0" :
            return "0"
        elif a == "1" :
            return b
        elif b == "1" :
            return a
        else :
            return "%s*%s" % (a,b)

    def negate(self, a) :
        if a == "0" :
            return "1"
        elif a == "1" :
            return "0"
        else :
            return "(1-%s)" % a 

    def value(self, a) :
        return str(a)
        
    def normalize(self, a, Z) :
        if Z == "1" :
            return a
        else :
            return "%s / %s" % (a,Z)


class Evaluator(object) :

    def __init__(self, formula, semiring) :
        self.formula = formula
        self.__semiring = semiring
        
        self.__evidence = []
        
    def _get_semiring(self) : return self.__semiring
    semiring = property(_get_semiring)
        
    def initialize(self) :
        raise NotImplementedError('Evaluator.initialize() is an abstract method.')
        
    def propagate(self) :
        raise NotImplementedError('Evaluator.propagate() is an abstract method.')
        
    def evaluate(self, index) :
        """Compute the value of the given node."""
        raise NotImplementedError('Evaluator.evaluate() is an abstract method.')
        
    def getZ(self) :
        """Get the normalization constant."""
        raise NotImplementedError('Evaluator.getZ() is an abstract method.')
        
    def addEvidence(self, node) :
        """Add evidence"""
        self.__evidence.append(node)
        
    def clearEvidence(self) :
        self.__evidence = []
        
    def iterEvidence(self) :
        return iter(self.__evidence)            
            
class SDDEvaluator(Evaluator):

    pass


class SimpleNNFEvaluator(Evaluator) :
    
    def __init__(self, formula, semiring) :
        Evaluator.__init__(self, formula, semiring)
        self.__nnf = formula        
        self.__probs = {}
        
        self.Z = 0
    
    def getNames(self, label=None) :
        return self.__nnf.getNames(label)
        
    def initialize(self) :
        self.__probs.clear()
        
        self.__probs.update(self.__nnf.extractWeights(self.semiring))
                        
        for ev in self.iterEvidence() :
            self.setEvidence( abs(ev), ev > 0 )
            
        self.Z = self.getZ()
                
    def propagate(self) :
        self.initialize()
        
    def getZ(self) :
        result = self.getWeight( len(self.__nnf) )
        return result
        
    def evaluate(self, node) :
        p = self.getWeight(abs(node))
        n = self.getWeight(-abs(node))
        self.setValue(abs(node), (node > 0) )
        result = self.getWeight( len(self.__nnf) )
        self.resetValue(abs(node),p,n)
        return self.semiring.normalize(result,self.Z)
        
    def resetValue(self, index, pos, neg) :
        self.setWeight( index, pos, neg)
            
    def getWeight(self, index) :
        if index == 0 :
            return self.semiring.one()
        elif index == None :
            return self.semiring.zero()
        else :
            pos_neg = self.__probs.get(abs(index))
            if pos_neg == None :
                p = self._calculateWeight( abs(index) )
                pos, neg = (p, self.semiring.negate(p))
            else :
                pos, neg = pos_neg
            if index < 0 :
                return neg
            else :
                return pos
                
    def setWeight(self, index, pos, neg) :
        self.__probs[index] = (pos, neg)
        
    def setEvidence(self, index, value ) :
        pos = self.semiring.one()
        neg = self.semiring.zero()
        if value :
            self.setWeight( index, pos, neg )
        else :
            self.setWeight( index, neg, pos )
            
    def setValue(self, index, value ) :
        if value :
            pos = self.getWeight(index)
            self.setWeight( index, pos, self.semiring.zero() )
        else :
            neg = self.getWeight(-index)
            self.setWeight( index, self.semiring.zero(), neg )

    def _calculateWeight(self, key) :
        assert(key != 0)
        assert(key != None)
        assert(key > 0) 
        
        node = self.__nnf._getNode(key)
        ntype = type(node).__name__
        assert(ntype != 'atom')
        
        childprobs = [ self.getWeight(c) for c in node.children ]
        if ntype == 'conj' :
            p = self.semiring.one()
            for c in childprobs :
                p = self.semiring.times(p,c)
            return p
        elif ntype == 'disj' :
            p = self.semiring.zero()
            for c in childprobs :
                p = self.semiring.plus(p,c)
            return p
        else :
            raise TypeError("Unexpected node type: '%s'." % nodetype)    


class CNF(object) :
    """A logic formula in Conjunctive Normal Form.
    
    This class does not derive from LogicFormula.
    
    """
    
    def __init__(self) :
        self.__names = []
        self.__constraints = []
        self.__weights = []
        
        self.__lines = []

    def getNamesWithLabel(self) :
        return self.__names

    def constraints(self) :
        return self.__constraints
        
    def getWeights(self) :
        return self.__weights
                
    @classmethod
    def createFrom(cls, formula, **extra) :
        cnf = CNF()
        
        lines = []
        for index, node in enumerate(formula) :
            index += 1
            nodetype = type(node).__name__
            
            if nodetype == 'conj' :
                line = str(index) + ' ' + ' '.join( map( lambda x : str(-(x)), node.children ) ) + ' 0'
                lines.append(line)
                for x in node.children  :
                    lines.append( "%s %s 0" % (-index, x) )
            elif nodetype == 'disj' :
                line = str(-index) + ' ' + ' '.join( map( lambda x : str(x), node.children ) ) + ' 0'
                lines.append(line)
                for x in node.children  :
                    lines.append( "%s %s 0" % (index, -x) )
            elif nodetype == 'atom' :
                pass
            else :
                raise ValueError("Unexpected node type: '%s'" % nodetype)
            
        for c in formula.constraints() :
            for l in c.encodeCNF() :
                lines.append(' '.join(map(str,l)) + ' 0')
        
        clause_count = len(lines)
        atom_count = len(formula)
        cnf.__lines = [ 'p cnf %s %s' % (atom_count, clause_count) ] + lines
        cnf.__names = formula.getNamesWithLabel()
        cnf.__constraints = formula.constraints()
        cnf.__weights = formula.getWeights()
        return cnf
        
    def toDimacs(self) :
        return '\n'.join( self.__lines )
    
class NNF(LogicFormula) :
    
    def __init__(self) :
        LogicFormula.__init__(self, auto_compact=False)

    @classmethod
    def createFrom(cls, formula, **extra) :
        assert( isinstance(formula, LogicProgram) or isinstance(formula, LogicFormula) or isinstance(formula, CNF) )
        if isinstance(formula, LogicProgram) :
            formula = ground(formula)

        # Invariant: formula is CNF or LogicFormula
        if not isinstance(formula, NNF) :
            if not isinstance(formula, CNF) :
                formula = CNF.createFrom(formula)
            # Invariant: formula is CNF
            return cls._compile(formula)
        else :
            # TODO force_copy??
            return formula
                        
    @classmethod
    def _compile(cls, cnf) :
        names = cnf.getNamesWithLabel()
        
        # TODO extract paths
        # TODO add alternative compiler support
        cnf_file = '/tmp/pl.cnf'
        with open(cnf_file, 'w') as f :
            f.write(cnf.toDimacs())

        nnf_file = '/tmp/pl.nnf'
        cmd = ['../version2.0/assist/darwin/dsharp', '-Fnnf', nnf_file, '-smoothNNF','-disableAllLits', cnf_file ] #

        OUT_NULL = open(os.devnull, 'w')

        attempts_left = 10
        success = False
        while attempts_left and not success :
            try :
                subprocess.check_call(cmd, stdout=OUT_NULL)
                success = True
            except subprocess.CalledProcessError as err :
                #print (err)
                #print ("dsharp crashed, retrying", file=sys.stderr)
                attempts_left -= 1
                if attempts_left == 0 :
                    raise err
        
        return cls._load_nnf( nnf_file, cnf)
    
    @classmethod
    def _load_nnf(cls, filename, cnf) :
        nnf = NNF()

        weights = cnf.getWeights()
        
        names_inv = defaultdict(list)
        for name,node,label in cnf.getNamesWithLabel() :
            names_inv[node].append((name,label))
        
        with open(filename) as f :
            line2node = {}
            rename = {}
            lnum = 0
            for line in f :
                line = line.strip().split()
                if line[0] == 'nnf' :
                    pass
                elif line[0] == 'L' :
                    name = int(line[1])
                    prob = weights.get(abs(name), True)
                    node = nnf.addAtom( abs(name), prob )
                    rename[abs(name)] = node
                    if name < 0 : node = -node
                    line2node[lnum] = node
                    if abs(name) in names_inv :
                        for actual_name, label in names_inv[abs(name)] :
                            if name < 0 :
                                nnf.addName(actual_name, -node, label)
                            else :
                                nnf.addName(actual_name, node, label)
                    lnum += 1
                elif line[0] == 'A' :
                    children = map(lambda x : line2node[int(x)] , line[2:])
                    line2node[lnum] = nnf.addAnd( children )
                    lnum += 1
                elif line[0] == 'O' :
                    children = map(lambda x : line2node[int(x)], line[3:])
                    line2node[lnum] = nnf.addOr( children )        
                    lnum += 1
                else :
                    print ('Unknown line type')
                    
        for c in cnf.constraints() :
            nnf.addConstraint(c.copy(rename))
                    
        return nnf
        
    def getEvaluator(self, semiring=None) :
        if semiring == None :
            semiring = SemiringProbability()
        
        evaluator = SimpleNNFEvaluator(self, semiring )

        for n_ev, node_ev in evaluator.getNames('evidence') :
            evaluator.addEvidence( node_ev )
        
        for n_ev, node_ev in evaluator.getNames('-evidence') :
            evaluator.addEvidence( -node_ev )

        evaluator.propagate()
        return evaluator
        
    def evaluate(self, index=None, semiring=None) :
        evaluator = self.getEvaluator(semiring)
        
        if index == None :
            result = {}
            # Probability of query given evidence
            for name, node in evaluator.getNames('query') :
                w = evaluator.evaluate(node)    
                if w < 1e-6 : 
                    result[name] = 0.0
                else :
                    result[name] = w
            return result
        else :
            return evaluator.evaluate(node)

