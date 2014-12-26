from __future__ import print_function

from collections import defaultdict

LABEL_QUERY = "query"
LABEL_EVIDENCE_POS = "evidence+"
LABEL_EVIDENCE_NEG = "evidence-"
LABEL_EVIDENCE_MAYBE = "evidence?"    


class ProbLog(object) :
    """This is a static class"""
    
    def __init__(self) :
        raise Exception("This is a static class!")
        
    transformations = defaultdict(list)    
        
    @classmethod
    def registerTransformation(cls, src, target, action=None) :
        cls.transformations[target].append( (src, action) )
    
    @classmethod
    def findPaths( cls, src, target, stack=() ) :
        # Create a destination object or any of its subclasses
        if isinstance(src, target) :
            yield (target,)
        else :
            # for d in cls.transformations :
            #     if issubclass(d,target) :
                    d = target
                    for s, action in cls.transformations[d] :
                        if not s in stack :                        
                            for path in cls.findPaths( src, s, stack+(s,) ) :
                                yield path + (action,d)
                # elif issubclass(target,d) :
                #     for s, action in cls.transformations[d] :
                #         if not s in stack :
                #             for path in cls.findPaths( src, s, stack+(s,) ) :
                #                 yield path + (action,cls)
    
    @classmethod
    def convert( cls, src, target ) :
        for path in cls.findPaths(src,target) :
            current_obj = src
            path = path[1:]
            while path :
                if path[1] != None :
                    next_obj = path[0]( current_obj, path[1]() )
                else :
                    next_obj = path[1].createFromDefaultAction(current_obj)
                path = path[2:]
                current_obj = next_obj
            return current_obj
        raise ProbLogError("No conversion strategy found from an object of class '%s' to an object of class '%s'." % ( type(src).__name__, target.__name__ ))

class ProbLogError(Exception) : pass

class ProbLogObject(object) :
    """Root class for all convertible objects in the ProbLog system."""


    @classmethod
    def createFrom(cls, obj) :
        return ProbLog.convert( obj, cls )

    @classmethod
    def createFromDefaultAction(cls, src) :
        raise ProbLogError("No default conversion strategy defined.")

class transform(object) :
    """Decorator"""
    
    def __init__(self, cls1, cls2, func=None) :
        self.cls1 = cls1
        self.cls2 = cls2
        if not issubclass(cls2, ProbLogObject) :
            raise TypeError("Conversion only possible for subclasses of ProbLogObject.")        
        if func != None :
            self(func)
        
    def __call__(self, f) :
        # TODO check type contract?
        ProbLog.registerTransformation( self.cls1, self.cls2, f )
        return f