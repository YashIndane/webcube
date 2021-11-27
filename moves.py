import kociemba

def get_moves(cs) :

  kociemba_string = kociemba.solve(cs)

  speaking_cmds = {

                 'L'   : 'Rotate left face clockwise',
                 'R'   : 'Rotate right face clockwise',
                 'U'   : 'Rotate top face clockwise',
                 'D'   : 'Rotate bottom face clockwise',
                 'F'   : 'Rotate front face clockwise',
                 'B'   : 'Rotate back face clockwise',
                 'L\'' : 'Rotate left face anticlockwise',
                 'R\'' : 'Rotate right face anticlockwise',
                 'U\'' : 'Rotate top face anticlockwise',
                 'D\'' : 'Rotate bottom face anticlockwise',
                 'F\'' : 'Rotate front face anticlokwise',
                 'B\'' : 'Rotate back face anticlockwise',
                 'L2'  : 'Rotate left face twice',
                 'R2'  : 'Rotate right face twice',
                 'U2'  : 'Rotate top face twice',
                 'D2'  : 'Rotate bottom face twice',
                 'F2'  : 'Rotate front face twice',
                 'B2'  : 'Rotate back face twice'

  }

  csa = kociemba_string.split(" ")
  
  final_commands = []
  for x in csa :
    final_commands.append(speaking_cmds[x])

  return final_commands