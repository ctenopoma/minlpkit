"""
Sudoku Solver (MIP Formulation)
This model solves a 9x9 Sudoku puzzle using integer programming.
Reference: Bartlett, A. C., Chartier, T. P., Langville, A. N., & Rankin, T. D. (2008). 
An integer programming model for the Sudoku problem. 
Journal of Online Mathematics and its Applications, 8(1), 1-13.
"""

from pyscipopt import Model

def build_model(infeasible=False):
    m = Model("Sudoku")
    
    # Dummy data: 9x9 Sudoku grid (0 means empty)
    # A simple valid puzzle
    board = [
        [5, 3, 0, 0, 7, 0, 0, 0, 0],
        [6, 0, 0, 1, 9, 5, 0, 0, 0],
        [0, 9, 8, 0, 0, 0, 0, 6, 0],
        [8, 0, 0, 0, 6, 0, 0, 0, 3],
        [4, 0, 0, 8, 0, 3, 0, 0, 1],
        [7, 0, 0, 0, 2, 0, 0, 0, 6],
        [0, 6, 0, 0, 0, 0, 2, 8, 0],
        [0, 0, 0, 4, 1, 9, 0, 0, 5],
        [0, 0, 0, 0, 8, 0, 0, 7, 9]
    ]
    
    if infeasible:
        board[0][0] = 5
        board[0][1] = 5 # Infeasible
        
    # Variables
    # x[i, j, v] = 1 if cell (i, j) has value v
    x = {}
    for i in range(9):
        for j in range(9):
            for v in range(1, 10):
                x[i, j, v] = m.addVar(vtype="B", name=f"x_{i}_{j}_{v}")
                
    # Objective: Feasibility problem, so 0
    m.setObjective(0, "minimize")
    
    # Constraints
    # 1. Each cell gets exactly one value
    for i in range(9):
        for j in range(9):
            m.addCons(sum(x[i, j, v] for v in range(1, 10)) == 1, name=f"Cell_{i}_{j}")
            
    # 2. Each row has unique values
    for i in range(9):
        for v in range(1, 10):
            m.addCons(sum(x[i, j, v] for j in range(9)) == 1, name=f"Row_{i}_val_{v}")
            
    # 3. Each col has unique values
    for j in range(9):
        for v in range(1, 10):
            m.addCons(sum(x[i, j, v] for i in range(9)) == 1, name=f"Col_{j}_val_{v}")
            
    # 4. Each 3x3 subgrid has unique values
    for block_i in range(3):
        for block_j in range(3):
            for v in range(1, 10):
                m.addCons(sum(x[block_i*3 + di, block_j*3 + dj, v] 
                              for di in range(3) for dj in range(3)) == 1, 
                          name=f"Block_{block_i}_{block_j}_val_{v}")
                
    # 5. Fix given values
    for i in range(9):
        for j in range(9):
            if board[i][j] != 0:
                m.addCons(x[i, j, board[i][j]] == 1, name=f"Given_{i}_{j}")
                
    return m

def main():
    m = build_model()
    m.optimize()
    if m.getStatus() == "optimal":
        print("Status:", m.getStatus())
    else:
        print("Status:", m.getStatus())

if __name__ == "__main__":
    main()
