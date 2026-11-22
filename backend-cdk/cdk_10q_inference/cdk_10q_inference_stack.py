from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_authorizers as authorizers,
)
from aws_cdk.aws_apigatewayv2_integrations import HttpLambdaIntegration
from constructs import Construct

MODEL_ID = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
MODEL_CONTEXT_WINDOW = 200_000
CONTEXT_BUDGET_RATIO = 0.8
SEC_USER_AGENT = "Roberto Ledesma robertoledesma015@gmail.com"

COGNITO_USER_POOL_ID = "us-east-1_0ErdpUNvW"
COGNITO_CLIENT_ID = "5thhkk3s3i62kpamf8f51v3nsq"


class Cdk10QInferenceStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        inference_fn = _lambda.Function(
            self, "InferenceFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="app.lambda_handler",
            code=_lambda.Code.from_asset("lambda"),
            timeout=Duration.minutes(5),
            memory_size=1024,
            environment={
                "MODEL_ID": MODEL_ID,
                "MODEL_CONTEXT_WINDOW": str(MODEL_CONTEXT_WINDOW),
                "CONTEXT_BUDGET_RATIO": str(CONTEXT_BUDGET_RATIO),
                "MAX_OUTPUT_TOKENS": "1024",
                "SEC_USER_AGENT": SEC_USER_AGENT,
            },
        )

        inference_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=["*"],
            )
        )

        # Edge Lambda
        edge_fn = _lambda.Function(
            self, "EdgeFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="app.lambda_handler",
            code=_lambda.Code.from_asset("edge_lambda"),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "CORE_FUNCTION_NAME": inference_fn.function_name,
            },
        )

        edge_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=[inference_fn.function_arn],
            )
        )

        issuer = f"https://cognito-idp.us-east-1.amazonaws.com/{COGNITO_USER_POOL_ID}"
        jwt_authorizer = authorizers.HttpJwtAuthorizer(
            "CognitoAuthorizer",
            jwt_issuer=issuer,
            jwt_audience=[COGNITO_CLIENT_ID],
        )

        integration = HttpLambdaIntegration("EdgeIntegration", edge_fn)

        api = apigwv2.HttpApi(
            self, "InferenceApi",
            api_name="partner-bot-api",
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_origins=["*"],
                allow_methods=[apigwv2.CorsHttpMethod.POST, apigwv2.CorsHttpMethod.OPTIONS],
                allow_headers=["Content-Type", "Authorization"],
            ),
        )

        api.add_routes(
            path="/inference",
            methods=[apigwv2.HttpMethod.POST],
            integration=integration,
            authorizer=jwt_authorizer,
        )

        CfnOutput(
            self, "ApiEndpoint",
            value=api.url + "inference",
            description="POST requests here with a Cognito JWT token.",
        )

        CfnOutput(
            self, "InferenceFunctionName",
            value=inference_fn.function_name,
        )