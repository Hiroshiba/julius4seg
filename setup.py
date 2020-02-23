from setuptools import setup, find_namespace_packages

setup(
    name='julius4seg',
    version='0.0.1',
    packages=find_namespace_packages(),
    url='https://github.com/Hiroshiba/julius4seg',
    author='Kazuyuki Hiroshiba',
    author_email='hihokaruta@gmail.com',
    license='MIT License',
    entry_points=dict(
        console_scripts=[
            'julius4seg_segment=sample.run_segment:main',
        ],
    ),
)
