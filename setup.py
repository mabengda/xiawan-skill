from setuptools import find_packages, setup


setup(
    name="xiawan-skill",
    version="0.1.0",
    description="Xiawan skill client for agent auth",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.9",
    install_requires=["websocket-client>=1.8,<2"],
    entry_points={
        "console_scripts": [
            "xiawan-skill=xiawan_skill.__main__:main",
            "xiawan-skill-lobby=xiawan_skill.launchers:lobby_entrypoint",
        ]
    },
)
