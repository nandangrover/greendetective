# Green Detective

Green Detective is a Django-based web application that helps detect and analyze greenwashing claims made by companies. It uses AI-powered analysis to evaluate environmental claims and generate detailed reports.

## Features

- AI-powered analysis of company websites and documents
- Greenwashing detection and scoring
- Detailed report generation in Excel format
- User authentication and invitation system
- API-first architecture with Django REST Framework
- Celery-based asynchronous task processing
- Vector similarity search using pgvector
- S3-compatible storage for reports

## Tech Stack

- Python 3.10
- Django 5.0
- Django REST Framework
- Celery
- PostgreSQL with pgvector
- Redis
- Docker & Docker Compose
- OpenAI API
- AWS S3 (or compatible storage)

## How to setup

### Docker

1. Install [Docker](https://docs.docker.com/get-docker/)
   - Make sure [buildkit](https://docs.docker.com/develop/develop-images/build_enhancements/#to-enable-buildkit-builds) is enabled
2. Copy `src/.env.local.template` and pasted as `src/.env` (if not existed)
3. Install pre-commit
   ```shell
   $ brew install pre-commit
   ```
4. Install pre-commit hooks
   ```shell
   $ pre-commit install --install-hooks
   ```
5. Build and run Docker
   ```shell
   $ docker-compose build
   $ docker-compose up
   ```

### Logging into an ECS service
1. Ensure `aws-cli`, `jq` and `session-manager-plugin` is installed
2. Configure aws-cli
```shell
# You will need your AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY. Set AWS_REGION to 'eu-west-2'
aws configure
```
3. Login into the service
```shell
# XYZ is the service name
$ ./aws-ecs-service.sh -s XYZ -f login
```
4. If you got this error: __Execute command is not enabled for XYZ__, then we need to enable that
```shell
$ ./aws-ecs-service.sh -s XYZ -f enable_execute_command
```

## Services

The application consists of several services:

- **API Service**: Main Django application (port 9000)
- **Process Service**: Celery worker for background tasks
- **Flower**: Celery monitoring interface (port 5556)
- **PostgreSQL**: Database (port 9500)
- **Redis**: Message broker and caching (port 9379)
- **LocalStack**: S3-compatible storage for local development (port 4566)
- **MailHog**: Email testing interface (ports 1025, 8025)


## Development Tools

- Pre-commit hooks for code quality
- Black for code formatting
- Ruff for linting
- Poetry for dependency management
- Coverage.py for test coverage

## Contributing

1. Create a feature branch from `sandbox`
2. Make your changes
3. Run tests and ensure code quality:

```bash
docker exec green-detective-service-api python manage.py test
```

4. Submit a pull request

## License

MIT License - see the [LICENSE](LICENSE) file for details

## Contact

Please contact us at [info@greendetective.earth](mailto:info@greendetective.earth)
