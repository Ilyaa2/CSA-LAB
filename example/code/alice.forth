  :intr intr_enter
    1 read
    dup 10 = if 1 stop_input ! 0 str_idx @ ! drop else
        str_idx @ !
        str_idx @ 1 + str_idx !
    then
  ei ;

  variable stop_input
  variable str_buff 40 allot
  variable str_idx

  str_buff str_idx !
  0 stop_input !

  2 ." enter your name: "
  begin stop_input @ until
  2 ." hello, "

  str_buff str_idx !
  begin str_idx @ @ dup
      0 =
      if drop 1 else
          2 emit
          str_idx @ 1 + str_idx ! 0
      then
  until

  2 ." !!!"