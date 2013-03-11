WARP
====

Simple http transparent proxy made in python 2.7.3 (can be run with pypy)

This is proof-of-concept code.


## Dependency
* python 2.7.3
* gevent >= 0.13.8

## How to use
1. run with python interpreter

        $ python warp.py

2. set browser's proxy setting to 

 [http proxy] host: 127.0.0.1 / port: 8800

3. ???

4. PROFIT!

### Command help
$ python warp.py --help

## License
MIT License (include in warp.py)

## 면책조항
1. WARP를 사용함으로써 생기는 모든 책임은 사용자에게 있습니다.
2. WARP의 코드 기여자들은 사용에 관한 책임을 지지 않습니다.

## Notice
1. may not work in
   * some ISPs
   * some company firewalls
   * some school firewalls
   * some browers (will fix it later)
