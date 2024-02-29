  : my-loop
      1 -
      begin
          dup
          2 mod 0 = if dup sum @ + sum ! then
          swap over +
          dup 4000000 >
      until
      sum @
  ;

  variable sum
  0 sum !
  1 2 my-loop
  3 emit