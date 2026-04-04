from .candidate_mst_solver import *
from .registry import register_solver


# @register_solver
class StaticFermatMSTSolver(CandidateMSTSolver):

    def __init__(self, request: SolverRequest):
        request.params['candidate_algorithm'] =  'fermat'
        super().__init__(request)