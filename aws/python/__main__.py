"""An AWS Python Pulumi program"""

import pulumi
import pulumi_aws as aws

config = pulumi.Config()
region = aws.config.region
instance_type = config.get("instance_type")
autoscale_min = config.get_int("autoscale_min")
autoscale_max = config.get_int("autoscale_max")
autoscale_desired = config.get_int("autoscale_desired")
prefix = config.get("prefix")
az = ["a", "b", "c"]

# VPC and subnets
vpc = aws.ec2.Vpc(
    resource_name=f"{prefix}-vpc",
    cidr_block="10.0.0.0/16",
    enable_dns_support=True,
    enable_dns_hostnames=True
)

public_subnet_1 = aws.ec2.Subnet(
    resource_name=f"{prefix}-public-subnet-1",
    cidr_block="10.0.1.0/24",
    vpc_id=vpc.id,
    availability_zone=region + az[0]
)

public_subnet_2 = aws.ec2.Subnet(
    resource_name=f"{prefix}-public-subnet-2",
    cidr_block="10.0.2.0/24",
    vpc_id=vpc.id,
    availability_zone=region + az[1]
)

private_subnet_1 = aws.ec2.Subnet(
    resource_name=f"{prefix}-private-subnet-1",
    cidr_block="10.0.3.0/24",
    vpc_id=vpc.id,
    availability_zone=region + az[0]
)

private_subnet_2 = aws.ec2.Subnet(
    resource_name=f"{prefix}-private-subnet-2",
    cidr_block="10.0.4.0/24",
    vpc_id=vpc.id,
    availability_zone=region + az[1]
)

# Internet gateway for the public subnets
igw = aws.ec2.InternetGateway(
    resource_name=f"{prefix}-igw",
    vpc_id=vpc.id
)

# NAT gateway resources for the public subnets
elastic_ip = aws.ec2.Eip(
    resource_name=f"{prefix}-elasticIP",
    associate_with_private_ip="10.0.0.5",
    domain="vpc",
    opts=pulumi.ResourceOptions(depends_on=[igw])
)

ngw = aws.ec2.NatGateway(
    resource_name=f"{prefix}-ngw",
    allocation_id=elastic_ip.id,
    subnet_id=public_subnet_1.id,
    opts=pulumi.ResourceOptions(depends_on=[elastic_ip])
)

# Route tables
public_route_table = aws.ec2.RouteTable(
    resource_name=f"{prefix}-public-route-table",
    vpc_id=vpc.id
)

private_route_table = aws.ec2.RouteTable(
    resource_name=f"{prefix}-private-route-table",
    vpc_id=vpc.id
)

# Route the public subnet traffic through the Internet Gateway
public_internet_igw_route = aws.ec2.Route(
    resource_name=f"{prefix}-public-internet-igw-route",
    route_table_id=public_route_table.id,
    gateway_id=igw.id,
    destination_cidr_block="0.0.0.0/0"
)

# Route NAT Gateway
nat_ngw_route = aws.ec2.Route(
    resource_name=f"{prefix}-nat-ngw-route",
    nat_gateway_id=ngw.id,
    destination_cidr_block="0.0.0.0/0"
)

# Associate the route tables to the subnets
public_route_1_assoc = aws.ec2.RouteTableAssociation(
    resource_name=f"{prefix}-public-route-1-assoc",
    route_table_id=public_route_table.id,
    subnet_id=public_subnet_1.id
)

public_route_2_assoc = aws.ec2.RouteTableAssociation(
    resource_name=f"{prefix}-public-route-2-assoc",
    route_table_id=public_route_table.id,
    subnet_id=public_subnet_2.id
)

private_route_1_assoc = aws.ec2.RouteTableAssociation(
    resource_name=f"{prefix}-private-route-1-assoc",
    route_table_id=private_route_table.id,
    subnet_id=private_subnet_1.id
)

private_route_2_assoc = aws.ec2.RouteTableAssociation(
    resource_name=f"{prefix}-private-route-2-assoc",
    route_table_id=private_route_table.id,
    subnet_id=private_subnet_2.id
)

