from setuptools import find_packages, setup

package_name = "tracker_pkg"


setup(
    name=package_name,
    version="0.0.1",
    packages=find_packages(exclude=["test"]),
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/" + package_name],
        ),
        (
            "share/" + package_name,
            ["package.xml"],
        ),
    ],
    install_requires=["setuptools"],
    tests_require=["pytest"],
    zip_safe=True,
    maintainer="LiYuan",
    maintainer_email="liyuan930519@gmail.com",
    description="Red-object tracker node for the object tracking system",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "tracker_node = tracker_pkg.tracker_node:main",
        ],
    },
)
