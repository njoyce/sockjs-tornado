import os
from setuptools import find_packages, setup

from pip.req import parse_requirements

try:
    license = open('LICENSE').read()
except:
    license = None


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


def get_requirements(filename):
    try:
        from pip.download import PipSession

        session = PipSession()
    except ImportError:
        session = None

    reqs = parse_requirements(filename, session=session)

    return [str(r.req) for r in reqs]


setup_args = dict(
    name='sockjs-tornado',
    version='2.0.0',
    maintainer='Nick Joyce',
    maintainer_email='nick@boxdesign.co.uk',
    packages=find_packages(),
    namespace_packages=['sockjs'],
    install_requires=get_requirements('requirements.txt'),
    url='https://gitlab.com/show-cast/sockjs-tornado/',
    description='SockJS Python server implementation on top of Tornado framework',
)


if __name__ == '__main__':
    setup(**setup_args)
