from setuptools import setup, find_packages

setup(
    name="user_manager",
    version="1.0.0",
    description="Django app for integrating Django project with CHI_AUTH system",
    url="https://github.com/Center-for-Health-Informatics/django_user_manager",
    author="John Meinken",
    author_email="meinkejf@ucmail.uc.edu",
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        "Django >= 2.0",
        "django-crispy-forms",
        "requests",
    ],
)