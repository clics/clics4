from setuptools import setup, find_packages


setup(
    name='lexibank_clics4',
    version='0.2.0',
    description='',
    author='',
    author_email='',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    keywords='',
    license='MIT',
    url='https://github.com/clics/clics4',
    py_modules=['lexibank_clics4'],
    packages=find_packages(where='.'),
    include_package_data=True,
    zip_safe=False,
    entry_points={
        'lexibank.dataset': [
            'clics4=lexibank_clics4:Dataset',
        ],
        'cldfbench.commands': [
            'clics4=clics4commands',
        ],
    },
    platforms='any',
    python_requires='>=3.6',
    install_requires=[
        'collabutils[googlesheets]',
        'cldfbench>=1.7.2',
        'cltoolkit>=0.1.1',
        'cldfviz>=0.3.0',
        'cldfzenodo',
        'pylexibank',
        'attrs>=18.2',
        'clldutils>=3.5',
        'cldfcatalog>=1.3',
        'csvw>=1.6',
        'pycldf',
        'uritemplate',
        'lingpy>=2.6.8',
        'pyclts>=3.1',
        "pyclics==3.1.0",
        "zenodo_client"
        #'cartopy',
        #'pillow',
        #'matplotlib',
        #'scipy',
        #"lingrex"
    ],
    extras_require={
        'dev': ['flake8', 'wheel', 'twine'],
        'test': [
            'pytest>=6',
            'pytest-mock',
            'pytest-cov',
            'pytest-cldf',
            'coverage',
        ],
    },
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy'
    ],
)
