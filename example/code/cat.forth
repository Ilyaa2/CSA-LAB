  :intr intr_func
    1 read
    dup 10 = if 1 stop_input ! else
      2 emit
    then
    ei
  ;

  variable stop_input
  0 stop_input !
  begin stop_input @ until