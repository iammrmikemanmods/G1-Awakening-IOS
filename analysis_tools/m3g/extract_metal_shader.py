#!/usr/bin/env python3
"""Extract the exact runtime M3G shader for an external Apple metal-compiler gate.

This does not compile or execute a shader, and does not claim a GPU result.
"""
import argparse
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--header',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    text=args.header.read_text(encoding='utf-8')
    start='R"G1M3G('
    stop=')G1M3G"'
    if text.count(start)!=1 or text.count(stop)!=1:
        raise ValueError('expected exactly one G1M3G raw shader literal')
    source=text.split(start,1)[1].split(stop,1)[0]
    if not source.startswith('\n#include <metal_stdlib>\n'):
        raise ValueError('unexpected M3G shader preamble')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(source,encoding='utf-8')


if __name__=='__main__':
    main()
