"""Geometric constraint problem and solver. Uses ClusterSolver for solving
problems incrementally."""

import vector
import math
from clsolver import PrototypeMethod, SelectionMethod
from clsolver3D import ClusterSolver3D 
from cluster import Rigid, Hedgehog
from configuration import Configuration 
from diagnostic import diag_print
from constraint import Constraint, ConstraintGraph
from notify import Notifier, Listener
from tolerance import tol_eq
from intersections import angle_3p, distance_2p
from selconstr import SelectionConstraint

# ----------- GeometricProblem -------------

class GeometricProblem (Notifier, Listener):
    """A geometric constraint problem with a prototype.
    
       A problem consists of point variables (just variables for short), prototype
       points for each variable and constraints.
       Variables are just names and can be any hashable object (recommend strings)
       Supported constraints are instances of DistanceConstraint,AngleConstraint,
       FixConstraint or SelectionConstraint.
       
       Prototype points are instances of vector.

       GeometricProblem listens for changes in constraint parameters and passes
       these changes, and changes in the system of constraints and the prototype, 
       to any other listerers (e.g. GeometricSolver) 

       instance attributes:
         cg         - a ConstraintGraph instance
         prototype  - a dictionary mapping variables to points

    """
    
    def __init__(self, dimension):
        """initialize a new problem"""
        Notifier.__init__(self)
        Listener.__init__(self)
        self.dimension = dimension
        self.prototype = {}
        self.cg = ConstraintGraph()

    def add_point(self, variable,pos):
        """add a point variable with a prototype position"""
        position = vector.vector(pos)
        if variable not in self.prototype:
            self.prototype[variable] = position
            self.cg.add_variable(variable)
        else:
            raise StandardError, "point already in problem"

    def set_point(self, variable, pos):
        """set prototype position of point variable"""
        position = vector.vector(pos)
        if variable in self.prototype:
            self.prototype[variable] = position
            self.send_notify(("set_point", (variable,position)))
        else:
            raise StandardError, "unknown point variable"

    def get_point(self, variable):
        """get prototype position of point variable"""
        if variable in self.prototype:
            return self.prototype[variable]
        else:
            raise StandardError, "unknown point variable"

    def has_point(self, variable):
         return variable in self.prototype
    
    def add_constraint(self, con):
        """add a constraint"""
        if isinstance(con, DistanceConstraint):
            for var in con.variables():
                if var not in self.prototype:
                    raise StandardError, "point variable not in problem"
            if self.get_distance(con.variables()[0],con.variables()[1]):
                raise StandardError, "distance already in problem"
            else: 
                con.add_listener(self)
                self.cg.add_constraint(con)
        elif isinstance(con, AngleConstraint):
            for var in con.variables():
                if var not in self.prototype:
                    raise StandardError, "point variable not in problem"
            if self.get_angle(con.variables()[0],con.variables()[1], con.variables()[2]):
                raise StandardError, "angle already in problem"
            else: 
                con.add_listener(self)
                self.cg.add_constraint(con)
        elif isinstance(con, RigidConstraint):
            for var in con.variables():
                if var not in self.prototype:
                    raise StandardError, "point variable not in problem"
            #if self.get_rigid(con.variables())
            #    raise StandardError, "rigid already in problem"
            #else:
            if True:
                con.add_listener(self)
                self.cg.add_constraint(con)
        elif isinstance(con, SelectionConstraint):
            for var in con.variables():
                if var not in self.prototype:
                    raise StandardError, "point variable not in problem"
            self.cg.add_constraint(con)
            self.send_notify(("add_selection_constraint", con))
        elif isinstance(con, FixConstraint):
            for var in con.variables():
                if var not in self.prototype:
                    raise StandardError, "point variable not in problem"
            if self.get_fix(con.variables()[0]):
                raise StandardError, "fix already in problem"
            self.cg.add_constraint(con)
        else:
            raise StandardError, "unsupported constraint type"

    def get_distance(self, a, b):
        """return the distance constraint on given points, or None"""
        on_a = self.cg.get_constraints_on(a)
        on_b = self.cg.get_constraints_on(b)
        on_ab = filter(lambda c: c in on_a and c in on_b, on_a)
        distances = filter(lambda c: isinstance(c, DistanceConstraint), on_ab)
        if len(distances) > 1:
            raise StandardError, "multiple constraints found"
        elif len(distances) == 1:
            return distances[0]
        else:
            return None
 
    def get_angle(self, a, b, c):
        """return the angle constraint on given points, or None"""
        on_a = self.cg.get_constraints_on(a)
        on_b = self.cg.get_constraints_on(b)
        on_c = self.cg.get_constraints_on(c)
        on_abc = filter(lambda x: x in on_a and x in on_b and x in on_c, on_a)
        angles = filter(lambda x: isinstance(x, AngleConstraint), on_abc)
        candidates = filter(lambda x: x.variables()[1] == b, angles)
        if len(candidates) > 1:
            raise StandardError, "multiple constraints found"
        elif len(candidates) == 1:
            return candidates[0]
        else:
            return None

    def get_fix(self, p):
        """return the fix constraint on given point, or None"""
        on_p = self.cg.get_constraints_on(p)
        fixes = filter(lambda x: isinstance(x, FixConstraint), on_p)
        if len(fixes) > 1:
            raise StandardError, "multiple constraints found"
        elif len(fixes) == 1:
            return fixes[0]
        else:
            return None

    def verify(self, solution):
        """returns true iff all constraints satisfied by given solution. 
           solution is a dictionary mapping variables (names) to values (points)"""
        if solution == None:
            sat = False
        else:
            sat = True
            for con in self.cg.constraints():
                solved = True
                for v in con.variables():
                    if v not in solution:
                        solved = False
                        break
                if not solved:
                    diag_print(str(con)+" not solved", "GeometricProblem.verify")
                    sat = False
                elif not con.satisfied(solution):
                    diag_print(str(con)+" not satisfied", "GeometricProblem.verify")
                    sat = False
        return sat
       
    def rem_point(self, var):
        """remove a point variable from the constraint system"""
        if var in self.prototype:
            self.cg.rem_variable(var)
            del self.prototype[var]
        else:
            raise StandardError, "variable "+str(var)+" not in problem."
            
    def rem_constraint(self, con):
        """remove a constraint from the constraint system"""
        if con in self.cg.constraints():
            if isinstance(con, SelectionConstraint): 
                self.send_notify(("rem_selection_constraint", con))
            self.cg.rem_constraint(con)
        else:
            raise StandardError, "no constraint "+str(con)+" in problem."

    def receive_notify(self, object, notify):
        """When notified of changed constraint parameters, pass on to listeners"""
        if isinstance(object, ParametricConstraint):
            (message, data) = notify
            if message == "set_parameter":
                self.send_notify(("set_parameter",(object,data)))
        #elif object == self.cg:
        #    self.send_notify(notify)

    def __str__(self):
        s = ""
        for v in self.prototype:
            s += v + " = " + str(self.prototype[v]) + "\n"
        for con in self.cg.constraints():
            s += str(con) + "\n"
        return s
 
#class GeometricProblem


# ---------- GeometricSolver --------------

class GeometricSolver (Listener):
    """The GeometricSolver monitors changes in a GeometricProblem and 
       maps any changes to corresponding changes in a GeometricCluster
    """

    # public methods
    def __init__(self, problem, use_prototype=True):
        """Create a new GeometricSolver instance
        
           keyword args
            problem        - the GeometricProblem instance to be monitored for changes
        """
        # init superclasses
        Listener.__init__(self)

        # init variables
        self.problem = problem
        self.dimension = problem.dimension
        self.cg = problem.cg   
        if self.problem.dimension == 2:
            self.dr = ClusterSolver2D()
        elif self.problem.dimension == 3:
            self.dr = ClusterSolver3D()
        else:
            raise StandardError, "Do not know how to solve problems of dimension > 3."
        self._map = {}
        
        # enable prototype based selection by default
        self.set_prototype_selection(use_prototype)

        # register 
        self.cg.add_listener(self)
        self.dr.add_listener(self)

        # create an initial fix cluster
        self.fixvars = []
        self.fixcluster = None

        # add variables
        for var in self.cg.variables():
            self._add_variable(var)
       
        # add constraints
        toadd = set(self.cg.constraints())

        # add selection constraints first. Prevents re-evaluation 
        for con in list(toadd):
            if isinstance(con, SelectionConstraint): 
                self._add_constraint(con)
                toadd.remove(con)

        # add distances first. Nicer decomposition in Rigids
        for con in list(toadd):
            if isinstance(con, DistanceConstraint): 
                self._add_constraint(con)
                toadd.remove(con)

        # add other constraints. 
        for con in toadd:
            self._add_constraint(con)

    def set_prototype_selection(self, enabled):
        self.dr.set_prototype_selection(enabled)

    def get_constrainedness(self):
        """Depricated. Use get_statis instead"""
        return self.get_status()
    #    toplevel = self.dr.top_level()
    #    if len(toplevel) > 1:
    #        return "under-constrained"
    #    elif len(toplevel) == 1:
    #        cluster = toplevel[0]
    #        if isinstance(cluster,Rigid):
    #            configurations = self.dr.get(cluster)
    #            if configurations == None:
    #                return "unsolved"
    #            elif len(configurations) > 0:
    #                return "well-constrained"
    #            else:
    #                return "over-constrained"
    #        else:
    #            return "under-constrained"
    #    elif len(toplevel) == 0:
    #        return "error"

    def get_result(self):
        """Depricated. Use get_cluster instead."""
        return self.get_cluster()  

    def get_cluster(self):
        """Returns a GeometricCluster (the root of a tree of clusters),
         describing the solutions and the decomposition of the problem."""
        map = {}   
        # map dr clusters
        for drcluster in self.dr.rigids():
            # create geo cluster and map to drcluster (and vice versa)
            geocluster = GeometricCluster()
            map[drcluster] = geocluster
            map[geocluster] = drcluster
            # determine variables
            for var in drcluster.vars:
                geocluster.variables.append(var)
            # determine solutions
            solutions = self.dr.get(drcluster)
            underconstrained = False
            if solutions != None:
                for solution in solutions:
                    geocluster.solutions.append(solution.map)
                    if solution.underconstrained:
                        underconstrained = True
            # determine flag
            if drcluster.overconstrained:
                geocluster.flag = GeometricCluster.S_OVER
            elif len(geocluster.solutions) == 0:
                geocluster.flag = GeometricCluster.I_OVER
            elif underconstrained:
                geocluster.flag = GeometricCluster.I_UNDER
            else:
                geocluster.flag = GeometricCluster.OK
                
        # determine subclusters
        for method in self.dr.methods():
                for out in method.outputs():
                    if isinstance(out, Rigid):
                        parent = map[out]
                        for inp in method.inputs():
                            if isinstance(inp, Rigid):
                                parent.subs.append(map[inp])
        
        # combine clusters due to selection
        if False:
            for method in self.dr.methods():
                if isinstance(method, PrototypeMethod):
                    incluster = method.inputs()[0]
                    outcluster = method.outputs()[0]
                    geoin = map[incluster]
                    geoout = map[outcluster]
                    geoout.subs = list(geoin.subs)
            for method in self.dr.methods():
                if isinstance(method, SelectionMethod): 
                    incluster = method.inputs()[0]
                    outcluster = method.outputs()[0]
                    geoin = map[incluster]
                    geoout = map[outcluster]
                    geoout.subs = list(geoin.subs)

        # determine top-level result 
        rigids = filter(lambda c: isinstance(c, Rigid), self.dr.top_level())
        if len(rigids) == 0:            
            # no variables in problem?
            result = GeometricCluster()
            result.variables = []
            result.subs = []
            result.solutions = []
            result.flags = GeometricCluster.UNSOLVED
        elif len(rigids) == 1:
            # structurally well constrained, or structurally overconstrained
            result = map[rigids[0]]
        else:
            # structurally underconstrained cluster
            result = GeometricCluster()
            result.flag = GeometricCluster.S_UNDER
            for rigid in rigids:
                result.subs.append(map[rigid])
        return result 

    def get_solutions(self):
        """Returns a list of Configurations, which will be empty if the
           problem has no solutions. Note: this method is
           cheaper but less informative than get_cluster. The
           list and the configurations should not be changed (since they are
           references to objects in the solver)."""
        rigids = filter(lambda c: isinstance(c, Rigid), self.dr.top_level())
        if len(rigids) != 0:   
            return self.dr.get(rigids[0])
        else:
            return []

    def get_status(self):
        """Returns a symbolic flag, one of:
            GeometricCluster.S_UNDER, 
            GeometricCluster.S_OVER,
            GeometricCluster.OK,
            GeometricCluster.UNSOLVED,
            GeometricCluster.EMPTY,
            GeometricCluster.I_OVER,
            GeometricCluster.I_UNDER.
           Note: this method is cheaper but less informative than get_cluster. 
        """
        rigids = filter(lambda c: isinstance(c, Rigid), self.dr.top_level())
        if len(rigids) == 0:            
            return GeometricCluster.EMPTY
        elif len(rigids) == 1:
            drcluster = rigids[0]
            solutions = self.dr.get(drcluster)
            underconstrained = False
            if solutions == None:
                return GeometricCluster.UNSOLVED
            else:
                for solution in solutions:
                    if solution.underconstrained:
                        underconstrained = True
            if drcluster.overconstrained:
                return GeometricCluster.S_OVER
            elif len(solutions) == 0:
                return GeometricCluster.I_OVER
            elif underconstrained:
                return GeometricCluster.I_UNDER
            else:
                return GeometricCluster.OK
        else:
            return GeometricCluster.S_UNDER
    
    def receive_notify(self, object, message):
        """Take notice of changes in constraint graph"""
        if object == self.cg:
            (type, data) = message
            if type == "add_constraint":
                self._add_constraint(data)
            elif type == "rem_constraint":
                self._rem_constraint(data)
            elif type == "add_variable":
                self._add_variable(data)
            elif type == "rem_variable":
                self._rem_variable(data)
            else:
                raise StandardError, "unknown message type"+str(type)
        elif object == self.problem:
            (type, data) = message
            if type == "set_point":
                (variable, point) = data
                self._update_variable(variable) 
            elif type == "set_parameter":
                (constraint, value) = data
                self._update_constraint(constraint)
            else:
                raise StandardError, "unknown message type"+str(type)
        elif object == self.dr:
            pass
        else:
            raise StandardError, "message from unknown source"+str((object, message))
    
    # internal methods

    def _add_variable(self, var):
        if var not in self._map:
            rigid = Rigid([var])
            self._map[var] = rigid
            self._map[rigid] = var
            self.dr.add(rigid)
            self._update_variable(var)
        
    def _rem_variable(self, var):
        diag_print("GeometricSolver._rem_variable","gcs")
        if var in self._map:
            self.dr.remove(self._map[var])
            del self._map[var]

    def _add_constraint(self, con):
        if isinstance(con, AngleConstraint):
            # map to hedgdehog
            vars = list(con.variables());
            hog = Hedgehog(vars[1],[vars[0],vars[2]])
            self._map[con] = hog
            self._map[hog] = con
            self.dr.add(hog)
            # set configuration
            self._update_constraint(con)
        elif isinstance(con, DistanceConstraint):
            # map to rigid
            vars = list(con.variables());
            rig = Rigid([vars[0],vars[1]])
            self._map[con] = rig
            self._map[rig] = con
            self.dr.add(rig)
            # set configuration
            self._update_constraint(con)
        elif isinstance(con, RigidConstraint):
            # map to rigid
            vars = list(con.variables());
            rig = Rigid(vars)
            self._map[con] = rig
            self._map[rig] = con
            self.dr.add(rig)
            # set configuration
            self._update_constraint(con)
        elif isinstance(con, FixConstraint):
            if self.fixcluster != None:
                self.dr.remove(self.fixcluster)
            self.fixvars.append(con.variables()[0])
            if len(self.fixvars) >= 1:
            #if len(self.fixvars) >= self.problem.dimension:
                self.fixcluster = Rigid(self.fixvars)
                self.dr.add(self.fixcluster)
                self.dr.set_root(self.fixcluster)
                self._update_fix()
        elif isinstance(con, SelectionConstraint):
            # add directly to clustersolver
            self.dr.add_selection_constraint(con)
        else:
            ## raise StandardError, "unknown constraint type"
            pass
         
    def _rem_constraint(self, con):
        diag_print("GeometricSolver._rem_constraint","gcs")
        if isinstance(con,FixConstraint):
            if self.fixcluster != None:
                self.dr.remove(self.fixcluster)
            var = con.variables()[0]
            if var in self.fixvars:
                self.fixvars.remove(var)
            #if len(self.fixvars) < self.problem.dimension:
            if len(self.fixvars) == 0:
                self.fixcluster = None
            else:
                self.fixcluster = Rigid(self.fixvars)
                self.dr.add(self.fixcluster)
                self.dr.set_root(self.fixcluster)
        elif isinstance(con, SelectionConstraint):
            # remove directly from clustersolver
            self.dr.rem_selection_constraint(con)
        elif con in self._map:
            self.dr.remove(self._map[con])
            del self._map[con]
  
    # update methods: set the value of the variables in the constraint graph

    def _update_constraint(self, con):
        if isinstance(con, AngleConstraint):
            # set configuration
            hog = self._map[con]
            vars = list(con.variables())
            v0 = vars[0]
            v1 = vars[1]
            v2 = vars[2]
            angle = con.get_parameter()
            p0 = vector.vector([1.0,0.0])
            p1 = vector.vector([0.0,0.0])
            p2 = vector.vector([math.cos(angle), math.sin(angle)])
            # pad vectors to right dimension
            if self.dimension == 3:
                p0.append(0.0)
                p1.append(0.0)
                p2.append(0.0)
            conf = Configuration({v0:p0,v1:p1,v2:p2})
            self.dr.set(hog, [conf])
            assert con.satisfied(conf.map)
        elif isinstance(con, DistanceConstraint):
            # set configuration
            rig = self._map[con]
            vars = list(con.variables())
            v0 = vars[0]
            v1 = vars[1]
            dist = con.get_parameter()
            p0 = vector.vector([0.0,0.0])
            p1 = vector.vector([dist,0.0])
            if self.dimension == 3:
                p0.append(0.0)
                p1.append(0.0)
            conf = Configuration({v0:p0,v1:p1})
            self.dr.set(rig, [conf])
            assert con.satisfied(conf.map)
        elif isinstance(con, RigidConstraint):
            # set configuration
            rig = self._map[con]
            vars = list(con.variables())
            conf = con.get_parameter()
            self.dr.set(rig, [conf])
            assert con.satisfied(conf.map)
        elif isinstance(con, FixConstraint):
            self._update_fix()
        else:
            raise StandardError, "unknown constraint type"
    
    def _update_variable(self, variable):
        cluster = self._map[variable]
        proto = self.problem.get_point(variable)
        conf = Configuration({variable:proto})
        self.dr.set(cluster, [conf])

    def _update_fix(self):
        if self.fixcluster:
            vars = self.fixcluster.vars
            map = {}
            for var in vars:
                map[var] = self.problem.get_fix(var).get_parameter()
            conf = Configuration(map)
            self.dr.set(self.fixcluster, [conf])
        else:
            diag_print("no fixcluster to update","geometric")
            pass
   
#class GeometricSolver


# ------------ GeometricCluster -------------

class GeometricCluster:
    """Represents the result of solving a GeometricProblem. A cluster is a list of 
       point variable names and a list of solutions for
       those variables. A solution is a dictionary mapping variable names to
       points. The cluster also keeps a list of sub-clusters (GeometricCluster)
       and a set of flags, indicating incidental/structural
       under/overconstrained
       
       instance attributes:
            variables       - a list of point variable names
            solutions       - a list of solutions. Each solution is a dictionary 
                              mapping variable names to vectors. 
            subs            - a list of sub-clusters 
            flag            - value                 meaning
                              OK                    well constrained
                              I_OVER                incicental over-constrained
                              I_UNDER               incidental under-constrained
                              S_OVER                structural overconstrained 
                              S_UNDER               structural underconstrained
                              UNSOLVED              unsolved (no input values)
                              EMPTY                 empty (no variables)
       """

    OK = "well-constrained"
    I_OVER = "incidental over-constrained"      
    I_UNDER = "incidental under-constrained" 
    S_OVER = "structral over-constrained"
    S_UNDER = "structural under-constrained"
    UNSOLVED = "unsolved"
    EMPTY = "empty"
   
    def __init__(self):
        """initialise an empty new cluster"""
        self.variables = []
        self.solutions = []
        self.subs = []
        self.flag = GeometricCluster.OK

    def __str__(self):
        return self._str_recursive()
 
    def _str_recursive(result, depth=0, done=None):
        # create indent
        spaces = ""
        for i in range(depth):
            spaces = spaces + "|"
        
        # make done
        if done == None:
            done = set()
       
        # recurse
        s = ""
        if result not in done:
            # this one is done...
            done.add(result)
            # recurse
            for sub in result.subs:
                s = s + sub._str_recursive(depth+1, done)
        elif len(result.subs) > 0:
            s = s + spaces + "|...\n" 

        # pritn cluster
        s = spaces + "cluster " + str(result.variables) + " " + str(result.flag) + " " + str(len(result.solutions)) + " solutions\n" + s
        
        return s
    # def

  
# --------------------- constraint types --------------------


class ParametricConstraint(Constraint, Notifier):
    """A constraint with a parameter and notification when parameter changes"""
    
    def __init__(self):
        """initialize ParametricConstraint"""
        Notifier.__init__(self)
        self._value = None

    def get_parameter(self):
        """get parameter value"""
        return self._value

    def set_parameter(self,value):
        """set parameter value and notify any listeners"""
        self._value = value
        self.send_notify(("set_parameter", value))

class FixConstraint(ParametricConstraint):
    """A constraint to fix a point relative to the coordinate system"""

    def __init__(self, var, pos):
        """Create a new FixConstraint instance
        
           keyword args:
            var    - a point variable name 
            pos    - the position parameter
        """
        ParametricConstraint.__init__(self)
        self._variables = [var]
        self.set_parameter(pos)

    def satisfied(self, mapping):
        """return True iff mapping from variable names to points satisfies constraint""" 
        point = mapping[self._variables[0]]
        if len(point) != len(self._value):
            diag_print("warning: FixConstraint.satisfied: vectors of unequal length", "geometric.FixConstraint.satisfied")
            return False
        result = True;
        for i in range(len(self._value)):
            result &= tol_eq(point[i], self._value[i])
        return result

    def __str__(self):
        return "FixConstraint("\
            +str(self._variables[0])+","\
            +str(self._value)+")"

class DistanceConstraint(ParametricConstraint):
    """A constraint on the Euclidean distance between two points"""
    
    def __init__(self, a, b, dist):
        """Create a new DistanceConstraint instance
        
           keyword args:
            a    - a point variable name 
            b    - a point variable name
            dist - the distance parameter value
        """
        ParametricConstraint.__init__(self)
        self._variables = [a,b]
        self.set_parameter(dist)
    
    def satisfied(self, mapping):
        """return True iff mapping from variable names to points satisfies constraint""" 
        a = mapping[self._variables[0]]
        b = mapping[self._variables[1]]
        result = tol_eq(distance_2p(a,b), self._value)
        return result

    def __str__(self):
        return "DistanceConstraint("\
            +str(self._variables[0])+","\
            +str(self._variables[1])+","\
            +str(self._value)+")"

class AngleConstraint(ParametricConstraint):
    """A constraint on the angle in point B of a triangle ABC"""
    
    def __init__(self, a, b, c, ang):
        """Create a new AngleConstraint instance. 
        
           keyword args:
            a    - a point variable name
            b    - a point variable name
            c    - a point variable name
            ang  - the angle parameter value
        """
        ParametricConstraint.__init__(self)
        self._variables = [a,b,c]
        self.set_parameter(ang)

    def satisfied(self, mapping):
        """return True iff mapping from variable names to points satisfies constraint""" 
        a = mapping[self._variables[0]]
        b = mapping[self._variables[1]]
        c = mapping[self._variables[2]]
        ang = angle_3p(a,b,c)
        if ang == None:
            result = False
            cmp = self._value
        else:
            if len(a) >= 3:
                cmp = abs(self._value)
            else:
                cmp = self._value
            result = tol_eq(ang, cmp)
        if result == False:
            diag_print("measured angle = "+str(ang)+", parameter value = "+str(cmp), "geometric")
        return result

    def __str__(self):
        return "AngleConstraint("\
            +str(self._variables[0])+","\
            +str(self._variables[1])+","\
            +str(self._variables[2])+","\
            +str(self._value)+")"

class RigidConstraint(ParametricConstraint):
    """A constraint to set the relative position of a set of points"""
    
    def __init__(self, conf):
        """Create a new DistanceConstraint instance
        
           keyword args:
            conf    - a Configuration 
        """
        ParametricConstraint.__init__(self)
        self._variables = list(conf.vars())
        self.set_parameter(conf.copy())  
    
    def satisfied(self, mapping):
        """return True iff mapping from variable names to points satisfies constraint""" 
        result = True
        conf = self._value
        for index in range(1,len(self._variables)-1):
            p1 = mapping[self._variables[index-1]]
            p2 = mapping[self._variables[index]]
            p3 = mapping[self._variables[index+1]]
            c1 = conf.map[self._variables[index-1]]
            c2 = conf.map[self._variables[index]]
            c3 = conf.map[self._variables[index+1]]
            result = tol_eq(distance_2p(p1,p2), distance_2p(c1,c2))
            result = tol_eq(distance_2p(p1,p3), distance_2p(c1,c3))
            result = tol_eq(distance_2p(p2,p3), distance_2p(c2,c3))
        return result

    def __str__(self):
        return "RigidConstraint("+str(self._variables)+")" 

