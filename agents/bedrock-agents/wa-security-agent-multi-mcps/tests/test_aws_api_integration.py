# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""
Unit tests for AWS API MCP Server Integration
Tests detailed resource analysis, service configuration analysis, and permission validation
"""

import json
import os

# Import the module under test
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.append(
    os.path.join(os.path.dirname(__file__), "..", "agent_config", "integrations")
)

from aws_api_integration import (
    ActionResult,
    AWSAPIIntegrationImpl,
    PermissionStatus,
    PermissionValidationResult,
    RemediationAction,
    RemediationActionType,
    ResourceConfig,
    ServiceAnalysis,
    create_aws_api_integration,
)


class TestAWSAPIIntegration:
    """Test suite for AWS API Integration"""

    @pytest.fixture
    def api_integration(self):
        """Create AWS API integration instance for testing"""
        return AWSAPIIntegrationImpl(
            region="us-east-1",
            cache_ttl=300,  # 5 minutes for testing
        )

    @pytest.fixture
    def mock_http_client(self):
        """Mock HTTP client for testing"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {"content": [{"text": json.dumps({"test": "data"})}]}
        }
        mock_client.post.return_value = mock_response
        return mock_client

    @pytest.fixture
    def sample_s3_config(self):
        """Sample S3 bucket configuration"""
        return {
            "BucketName": "test-bucket",
            "Region": "us-east-1",
            "BucketEncryption": {
                "Rules": [
                    {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
                ]
            },
            "PublicAccessBlock": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            },
            "BucketVersioning": {"Status": "Enabled"},
            "Tags": {"Environment": "test", "Owner": "security-team"},
        }

    @pytest.fixture
    def sample_ec2_config(self):
        """Sample EC2 instance configuration"""
        return {
            "InstanceId": "i-1234567890abcdef0",
            "InstanceType": "t3.micro",
            "State": {"Name": "running"},
            "SecurityGroups": [
                {
                    "GroupId": "sg-12345678",
                    "GroupName": "test-sg",
                    "IpPermissions": [
                        {
                            "IpProtocol": "tcp",
                            "FromPort": 22,
                            "ToPort": 22,
                            "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                        }
                    ],
                }
            ],
            "IamInstanceProfile": {
                "Arn": "arn:aws:iam::123456789012:instance-profile/test-profile"
            },
            "Monitoring": {"State": "disabled"},
            "Tags": [
                {"Key": "Name", "Value": "test-instance"},
                {"Key": "Environment", "Value": "test"},
            ],
        }

    @pytest.fixture
    def sample_remediation_action(self):
        """Sample remediation action"""
        return {
            "action_id": "remediate-001",
            "action_type": "enable_encryption",
            "target_resource": "arn:aws:s3:::test-bucket",
            "description": "Enable encryption for S3 bucket",
            "parameters": {
                "encryption_config": {"SSEAlgorithm": "AES256"},
                "dry_run": False,
            },
            "safety_checks": ["verify_resource_exists", "check_existing_configuration"],
            "requires_approval": True,
        }

    def test_initialization(self, api_integration):
        """Test AWS API integration initialization"""
        assert api_integration.region == "us-east-1"
        assert api_integration.cache_ttl == 300
        assert hasattr(api_integration, "mcp_url")
        assert hasattr(api_integration, "mcp_headers")
        assert hasattr(api_integration, "service_resource_mappings")
        assert hasattr(api_integration, "security_attributes")
        assert hasattr(api_integration, "remediation_templates")

    def test_factory_function(self):
        """Test factory function for creating integration instance"""
        integration = create_aws_api_integration(region="us-west-2", cache_ttl=600)
        assert isinstance(integration, AWSAPIIntegrationImpl)
        assert integration.region == "us-west-2"
        assert integration.cache_ttl == 600

    def test_parse_arn_valid(self, api_integration):
        """Test ARN parsing with valid ARNs"""
        # Test S3 bucket ARN
        s3_arn = "arn:aws:s3:::test-bucket"
        s3_parts = api_integration._parse_arn(s3_arn)
        assert s3_parts["service"] == "s3"
        assert s3_parts["resource_id"] == "test-bucket"
        assert s3_parts["region"] == ""

        # Test EC2 instance ARN
        ec2_arn = "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0"
        ec2_parts = api_integration._parse_arn(ec2_arn)
        assert ec2_parts["service"] == "ec2"
        assert ec2_parts["region"] == "us-east-1"
        assert ec2_parts["account_id"] == "123456789012"
        assert ec2_parts["resource_type"] == "instance"
        assert ec2_parts["resource_id"] == "i-1234567890abcdef0"

    def test_parse_arn_invalid(self, api_integration):
        """Test ARN parsing with invalid ARNs"""
        invalid_arns = ["invalid-arn", "arn:aws:s3", "arn:aws", ""]

        for invalid_arn in invalid_arns:
            result = api_integration._parse_arn(invalid_arn)
            assert result is None

    def test_analyze_compliance_status_s3(self, api_integration, sample_s3_config):
        """Test compliance status analysis for S3 bucket"""
        # Test secure S3 configuration
        compliance_status = api_integration._analyze_compliance_status(
            sample_s3_config, "s3"
        )
        assert compliance_status["compliance_score"] > 80
        assert len(compliance_status["findings"]) == 0

        # Test insecure S3 configuration
        insecure_config = sample_s3_config.copy()
        insecure_config["PublicAccessBlock"]["BlockPublicAcls"] = False
        del insecure_config["BucketEncryption"]

        compliance_status = api_integration._analyze_compliance_status(
            insecure_config, "s3"
        )
        assert compliance_status["compliance_score"] < 80
        assert len(compliance_status["findings"]) > 0
        assert len(compliance_status["gaps"]) > 0

    def test_analyze_compliance_status_ec2(self, api_integration, sample_ec2_config):
        """Test compliance status analysis for EC2 instance"""
        compliance_status = api_integration._analyze_compliance_status(
            sample_ec2_config, "ec2"
        )

        # Should find security group issue (0.0.0.0/0 access)
        assert len(compliance_status["findings"]) > 0
        finding = compliance_status["findings"][0]
        assert "security group" in finding["finding"].lower()
        assert finding["severity"] == "MEDIUM"

    def test_generate_security_recommendations_s3(self, api_integration):
        """Test security recommendations generation for S3"""
        # Test S3 without encryption
        config_without_encryption = {
            "BucketName": "test-bucket",
            "BucketVersioning": {"Status": "Suspended"},
        }

        recommendations = api_integration._generate_security_recommendations(
            config_without_encryption, "s3"
        )

        # Should recommend encryption and versioning
        assert len(recommendations) >= 2
        encryption_rec = next(
            (r for r in recommendations if r["category"] == "encryption"), None
        )
        assert encryption_rec is not None
        assert encryption_rec["actionable"] is True

        versioning_rec = next(
            (r for r in recommendations if r["category"] == "data_protection"), None
        )
        assert versioning_rec is not None

    def test_generate_security_recommendations_ec2(
        self, api_integration, sample_ec2_config
    ):
        """Test security recommendations generation for EC2"""
        recommendations = api_integration._generate_security_recommendations(
            sample_ec2_config, "ec2"
        )

        # Should recommend enabling detailed monitoring
        monitoring_rec = next(
            (r for r in recommendations if r["category"] == "monitoring"), None
        )
        assert monitoring_rec is not None
        assert monitoring_rec["actionable"] is True
        assert monitoring_rec["remediation_action"] == "enable_detailed_monitoring"

    def test_calculate_resource_security_score(self, api_integration):
        """Test resource security score calculation"""
        # Test resource with no issues
        good_config = {"compliance_status": {"findings": [], "gaps": []}}
        score = api_integration._calculate_resource_security_score(good_config)
        assert score == 100.0

        # Test resource with high severity finding
        bad_config = {
            "compliance_status": {
                "findings": [{"severity": "HIGH"}],
                "gaps": ["missing_encryption"],
            }
        }
        score = api_integration._calculate_resource_security_score(bad_config)
        assert score == 65.0  # 100 - 25 (HIGH) - 10 (gap)

    def test_validate_remediation_action(
        self, api_integration, sample_remediation_action
    ):
        """Test remediation action validation"""
        # Test valid action
        assert (
            api_integration._validate_remediation_action(sample_remediation_action)
            is True
        )

        # Test invalid action (missing required fields)
        invalid_action = sample_remediation_action.copy()
        del invalid_action["action_id"]
        assert api_integration._validate_remediation_action(invalid_action) is False

        # Test invalid action (missing target_resource)
        invalid_action = sample_remediation_action.copy()
        del invalid_action["target_resource"]
        assert api_integration._validate_remediation_action(invalid_action) is False

    def test_validate_action_parameters(self, api_integration):
        """Test action parameter validation"""
        # Test enable_encryption action with valid parameters
        encryption_action = {
            "action_type": "enable_encryption",
            "parameters": {"encryption_config": {"SSEAlgorithm": "AES256"}},
        }
        assert api_integration._validate_action_parameters(encryption_action) is True

        # Test enable_encryption action with invalid parameters
        invalid_encryption_action = {
            "action_type": "enable_encryption",
            "parameters": {
                "encryption_config": {}  # Missing SSEAlgorithm
            },
        }
        assert (
            api_integration._validate_action_parameters(invalid_encryption_action)
            is False
        )

        # Test update_security_group action with valid parameters
        sg_action = {
            "action_type": "update_security_group",
            "parameters": {
                "security_group_id": "sg-12345678",
                "rules": [{"protocol": "tcp", "port": 80}],
            },
        }
        assert api_integration._validate_action_parameters(sg_action) is True

    def test_is_cache_valid(self, api_integration):
        """Test cache validity checking"""
        # Test empty cache
        assert api_integration._is_cache_valid("test_key", {}) is False

        # Test valid cache entry
        current_time = datetime.now().timestamp()
        cache_dict = {
            "test_key": {
                "data": {"test": "data"},
                "timestamp": current_time - 100,  # 100 seconds ago
            }
        }
        assert api_integration._is_cache_valid("test_key", cache_dict) is True

        # Test expired cache entry
        cache_dict["test_key"]["timestamp"] = (
            current_time - 400
        )  # 400 seconds ago (> 300 TTL)
        assert api_integration._is_cache_valid("test_key", cache_dict) is False

    @pytest.mark.asyncio
    async def test_get_detailed_resource_config_success(
        self, api_integration, mock_http_client, sample_s3_config
    ):
        """Test successful resource configuration retrieval"""

        # Mock the _get_resource_configuration method directly to avoid MCP complexity
        async def mock_get_resource_config(arn_parts):
            return sample_s3_config

        api_integration._get_resource_configuration = mock_get_resource_config

        # Test S3 bucket configuration retrieval
        result = await api_integration.get_detailed_resource_config(
            "arn:aws:s3:::test-bucket"
        )

        assert result["resource_arn"] == "arn:aws:s3:::test-bucket"
        assert result["service"] == "s3"
        assert result["configuration"] == sample_s3_config
        assert "security_attributes" in result
        assert "compliance_status" in result
        assert "recommendations" in result

    @pytest.mark.asyncio
    async def test_get_detailed_resource_config_invalid_arn(self, api_integration):
        """Test resource configuration retrieval with invalid ARN"""
        result = await api_integration.get_detailed_resource_config("invalid-arn")

        assert "error" in result
        assert result["error"] == "Invalid ARN format"

    @pytest.mark.asyncio
    async def test_get_detailed_resource_config_api_error(
        self, api_integration, mock_http_client
    ):
        """Test resource configuration retrieval with API error"""
        # Mock initialization failure
        api_integration.is_initialized = False

        # Mock the initialize method to fail
        async def mock_initialize():
            return False

        api_integration.initialize = mock_initialize

        result = await api_integration.get_detailed_resource_config(
            "arn:aws:s3:::test-bucket"
        )

        assert "error" in result
        assert "Failed to retrieve resource configuration" in result["error"]

    @pytest.mark.asyncio
    async def test_analyze_service_configuration_success(
        self, api_integration, mock_http_client, sample_s3_config
    ):
        """Test successful service configuration analysis"""
        # Mock resource discovery
        api_integration.http_client = mock_http_client

        # Mock resource list response
        resource_list = [{"arn": "arn:aws:s3:::test-bucket"}]
        mock_http_client.post.side_effect = [
            # First call: resource discovery
            MagicMock(
                status_code=200,
                json=lambda: {
                    "result": {"content": [{"text": json.dumps(resource_list)}]}
                },
            ),
            # Second call: resource configuration
            MagicMock(
                status_code=200,
                json=lambda: {
                    "result": {"content": [{"text": json.dumps(sample_s3_config)}]}
                },
            ),
        ]

        result = await api_integration.analyze_service_configuration("s3", "us-east-1")

        assert result["service_name"] == "s3"
        assert result["region"] == "us-east-1"
        assert "resources" in result
        assert "security_findings" in result
        assert "compliance_gaps" in result
        assert "recommendations" in result
        assert "overall_security_score" in result
        assert "summary" in result

    @pytest.mark.asyncio
    async def test_execute_remediation_action_success(
        self, api_integration, mock_http_client, sample_remediation_action
    ):
        """Test successful remediation action execution"""
        api_integration.http_client = mock_http_client

        # Mock successful remediation response
        remediation_result = {
            "success": True,
            "message": "Encryption enabled successfully",
            "changes_made": [
                {"resource": "test-bucket", "change": "encryption_enabled"}
            ],
        }
        mock_http_client.post.return_value.json.return_value = {
            "result": {"content": [{"text": json.dumps(remediation_result)}]}
        }

        # Mock safety checks to pass
        with patch.object(api_integration, "_perform_safety_checks") as mock_safety:
            mock_safety.return_value = {
                "passed": True,
                "message": "All checks passed",
                "warnings": [],
            }

            result = await api_integration.execute_remediation_action(
                sample_remediation_action
            )

            assert result["success"] is True
            assert result["action_id"] == "remediate-001"
            assert "changes_made" in result
            assert result["execution_time"] > 0

    @pytest.mark.asyncio
    async def test_execute_remediation_action_safety_check_failure(
        self, api_integration, sample_remediation_action
    ):
        """Test remediation action execution with safety check failure"""
        # Mock safety checks to fail
        with patch.object(api_integration, "_perform_safety_checks") as mock_safety:
            mock_safety.return_value = {
                "passed": False,
                "message": "Resource does not exist",
                "warnings": ["Target resource not found"],
            }

            result = await api_integration.execute_remediation_action(
                sample_remediation_action
            )

            assert result["success"] is False
            assert "Safety checks failed" in result["message"]
            assert "warnings" in result

    @pytest.mark.asyncio
    async def test_validate_permissions_success(
        self, api_integration, mock_http_client
    ):
        """Test successful permission validation"""
        api_integration.http_client = mock_http_client

        # Mock permission validation response
        permission_results = {
            "s3:GetBucketEncryption": {"decision": "allowed"},
            "s3:PutBucketEncryption": {"decision": "allowed"},
            "iam:SimulatePrincipalPolicy": {
                "decision": "denied",
                "reason": "Insufficient permissions",
            },
        }
        mock_http_client.post.return_value.json.return_value = {
            "result": {"content": [{"text": json.dumps(permission_results)}]}
        }

        required_permissions = [
            "s3:GetBucketEncryption",
            "s3:PutBucketEncryption",
            "iam:SimulatePrincipalPolicy",
        ]
        result = await api_integration.validate_permissions(required_permissions)

        assert result["overall_status"] == "partial"
        assert len(result["missing_permissions"]) == 1
        assert "iam:SimulatePrincipalPolicy" in result["missing_permissions"]
        assert "summary" in result
        assert result["summary"]["total_permissions"] == 3
        assert result["summary"]["granted_permissions"] == 2
        assert result["summary"]["denied_permissions"] == 1

    @pytest.mark.asyncio
    async def test_validate_permissions_all_granted(
        self, api_integration, mock_http_client
    ):
        """Test permission validation with all permissions granted"""
        api_integration.http_client = mock_http_client

        # Mock all permissions granted
        permission_results = {
            "s3:GetBucketEncryption": {"decision": "allowed"},
            "s3:PutBucketEncryption": {"decision": "allowed"},
        }
        mock_http_client.post.return_value.json.return_value = {
            "result": {"content": [{"text": json.dumps(permission_results)}]}
        }

        required_permissions = ["s3:GetBucketEncryption", "s3:PutBucketEncryption"]
        result = await api_integration.validate_permissions(required_permissions)

        assert result["overall_status"] == "granted"
        assert len(result["missing_permissions"]) == 0

    @pytest.mark.asyncio
    async def test_validate_permissions_all_denied(
        self, api_integration, mock_http_client
    ):
        """Test permission validation with all permissions denied"""
        api_integration.http_client = mock_http_client

        # Mock all permissions denied
        permission_results = {
            "s3:GetBucketEncryption": {"decision": "denied"},
            "s3:PutBucketEncryption": {"decision": "denied"},
        }
        mock_http_client.post.return_value.json.return_value = {
            "result": {"content": [{"text": json.dumps(permission_results)}]}
        }

        required_permissions = ["s3:GetBucketEncryption", "s3:PutBucketEncryption"]
        result = await api_integration.validate_permissions(required_permissions)

        assert result["overall_status"] == "denied"
        assert len(result["missing_permissions"]) == 2

    @pytest.mark.asyncio
    async def test_perform_safety_checks(self, api_integration):
        """Test safety checks execution"""
        action = {
            "action_type": "enable_encryption",
            "target_resource": "arn:aws:s3:::test-bucket",
            "safety_checks": ["verify_resource_exists", "validate_parameters"],
            "parameters": {"encryption_config": {"SSEAlgorithm": "AES256"}},
        }

        # Mock resource existence check
        with patch.object(api_integration, "_verify_resource_exists") as mock_verify:
            mock_verify.return_value = True

            result = await api_integration._perform_safety_checks(action)

            assert result["passed"] is True
            assert "check_details" in result
            assert len(result["check_details"]) == 2

    @pytest.mark.asyncio
    async def test_verify_resource_exists(
        self, api_integration, mock_http_client, sample_s3_config
    ):
        """Test resource existence verification"""
        api_integration.http_client = mock_http_client
        mock_http_client.post.return_value.json.return_value = {
            "result": {"content": [{"text": json.dumps(sample_s3_config)}]}
        }

        # Test existing resource
        exists = await api_integration._verify_resource_exists(
            "arn:aws:s3:::test-bucket"
        )
        assert exists is True

        # Test non-existing resource (API error)
        mock_http_client.post.return_value.status_code = 404
        exists = await api_integration._verify_resource_exists(
            "arn:aws:s3:::non-existent-bucket"
        )
        assert exists is False

    @pytest.mark.asyncio
    async def test_check_configuration_change_needed(
        self, api_integration, mock_http_client
    ):
        """Test configuration change necessity check"""
        # Mock resource without encryption
        config_without_encryption = {"BucketName": "test-bucket"}
        api_integration.http_client = mock_http_client
        mock_http_client.post.return_value.json.return_value = {
            "result": {"content": [{"text": json.dumps(config_without_encryption)}]}
        }

        action = {
            "action_type": "enable_encryption",
            "target_resource": "arn:aws:s3:::test-bucket-no-encryption",
        }

        needed = await api_integration._check_configuration_change_needed(action)
        assert needed is True

        # Mock resource with encryption already enabled (use different bucket to avoid cache)
        config_with_encryption = {
            "BucketName": "test-bucket-encrypted",
            "BucketEncryption": {
                "Rules": [
                    {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
                ]
            },
        }
        mock_http_client.post.return_value.json.return_value = {
            "result": {"content": [{"text": json.dumps(config_with_encryption)}]}
        }

        action_encrypted = {
            "action_type": "enable_encryption",
            "target_resource": "arn:aws:s3:::test-bucket-encrypted",
        }

        needed = await api_integration._check_configuration_change_needed(
            action_encrypted
        )
        assert needed is False

    @pytest.mark.asyncio
    async def test_close(self, api_integration, mock_http_client):
        """Test closing the integration"""
        api_integration.http_client = mock_http_client
        await api_integration.close()
        mock_http_client.aclose.assert_called_once()

    def test_fallback_methods(self, api_integration):
        """Test fallback methods when API calls fail"""
        # Test fallback resource config
        fallback_config = api_integration._get_fallback_resource_config(
            "arn:aws:s3:::test-bucket"
        )
        assert "error" in fallback_config
        assert fallback_config["service"] == "s3"

        # Test fallback service analysis
        fallback_analysis = api_integration._get_fallback_service_analysis(
            "s3", "us-east-1"
        )
        assert "error" in fallback_analysis
        assert fallback_analysis["service_name"] == "s3"
        assert fallback_analysis["region"] == "us-east-1"

        # Test fallback permission validation
        permissions = ["s3:GetBucketEncryption"]
        fallback_validation = api_integration._get_fallback_permission_validation(
            permissions
        )
        assert "error" in fallback_validation
        assert fallback_validation["overall_status"] == "unknown"
        assert len(fallback_validation["missing_permissions"]) == 1


class TestDataClasses:
    """Test data classes and enums"""

    def test_remediation_action_type_enum(self):
        """Test RemediationActionType enum"""
        assert RemediationActionType.ENABLE_ENCRYPTION.value == "enable_encryption"
        assert (
            RemediationActionType.UPDATE_SECURITY_GROUP.value == "update_security_group"
        )
        assert RemediationActionType.ENABLE_LOGGING.value == "enable_logging"

    def test_permission_validation_result_enum(self):
        """Test PermissionValidationResult enum"""
        assert PermissionValidationResult.GRANTED.value == "granted"
        assert PermissionValidationResult.DENIED.value == "denied"
        assert PermissionValidationResult.PARTIAL.value == "partial"
        assert PermissionValidationResult.UNKNOWN.value == "unknown"

    def test_resource_config_dataclass(self):
        """Test ResourceConfig dataclass"""
        config = ResourceConfig(
            resource_arn="arn:aws:s3:::test-bucket",
            resource_type="bucket",
            service="s3",
            region="us-east-1",
            configuration={"test": "data"},
            security_attributes={"encryption": True},
            compliance_status={"score": 95},
        )

        assert config.resource_arn == "arn:aws:s3:::test-bucket"
        assert config.service == "s3"
        assert config.configuration["test"] == "data"

    def test_service_analysis_dataclass(self):
        """Test ServiceAnalysis dataclass"""
        analysis = ServiceAnalysis(
            service_name="s3",
            region="us-east-1",
            resources=[],
            security_findings=[],
            compliance_gaps=[],
            recommendations=[],
            overall_security_score=85.5,
            analysis_timestamp="2024-01-01T00:00:00Z",
        )

        assert analysis.service_name == "s3"
        assert analysis.overall_security_score == 85.5
        assert isinstance(analysis.resources, list)

    def test_remediation_action_dataclass(self):
        """Test RemediationAction dataclass"""
        action = RemediationAction(
            action_id="test-001",
            action_type=RemediationActionType.ENABLE_ENCRYPTION,
            target_resource="arn:aws:s3:::test-bucket",
            description="Enable encryption",
            parameters={"algorithm": "AES256"},
            safety_checks=["verify_resource"],
        )

        assert action.action_id == "test-001"
        assert action.action_type == RemediationActionType.ENABLE_ENCRYPTION
        assert action.requires_approval is True  # default value

    def test_action_result_dataclass(self):
        """Test ActionResult dataclass"""
        result = ActionResult(
            action_id="test-001",
            success=True,
            message="Action completed successfully",
            changes_made=[{"resource": "bucket", "change": "encryption_enabled"}],
        )

        assert result.action_id == "test-001"
        assert result.success is True
        assert len(result.changes_made) == 1
        assert result.warnings is None  # default value

    def test_permission_status_dataclass(self):
        """Test PermissionStatus dataclass"""
        status = PermissionStatus(
            overall_status=PermissionValidationResult.GRANTED,
            permission_details={"s3:GetBucket": {"decision": "allowed"}},
            missing_permissions=[],
            recommendations=[],
            validation_timestamp="2024-01-01T00:00:00Z",
        )

        assert status.overall_status == PermissionValidationResult.GRANTED
        assert len(status.missing_permissions) == 0
        assert isinstance(status.permission_details, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
