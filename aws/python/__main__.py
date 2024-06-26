"""An AWS Python Pulumi program"""

import pulumi
import pulumi_aws as aws
import pulumi_tls as tls

config = pulumi.Config()
region = aws.config.region
autoscale_min = config.get_int("autoscale_min")
autoscale_max = config.get_int("autoscale_max")
autoscale_desired = config.get_int("autoscale_desired")
prefix = config.get("prefix")
az = ["a", "b", "c"]
ubuntu_ami = "ami-0705384c0b33c194c"
init_script = """
#!/bin/bash -xe
sudo apt update -y
sudo apt -y install docker
sudo service docker start
sudo usermod -a -G docker ec2-user
sudo chmod 666 /var/run/docker.sock
docker pull nginx
docker tag nginx my-nginx
docker run --rm --name nginx-server -d -p 80:80 -t my-nginx
"""

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
    route_table_id=private_route_table.id,
    nat_gateway_id=ngw.id,
    destination_cidr_block="0.0.0.0/0",
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

# Security groups

# ALB Security Group (Internet Traffic -> ALB)
lb_sg = aws.ec2.SecurityGroup(
    resource_name=f"{prefix}-lb-SecurityGroup",
    description="Controls access to the ALB",
    vpc_id=vpc.id,
    ingress=[aws.ec2.SecurityGroupIngressArgs(
        from_port=80,
        to_port=80,
        protocol="Tcp",
        cidr_blocks=["0.0.0.0/0"]
    )],
    egress=[aws.ec2.SecurityGroupEgressArgs(
        from_port=0,
        to_port=0,
        protocol="-1",
        cidr_blocks=["0.0.0.0/0"]
    )]
)

# Instance Security Group (ALB traffic -> EC2, ssh -> EC2)
ec2_sg = aws.ec2.SecurityGroup(
    resource_name=f"{prefix}-ec2-SecurityGroup",
    description="Allows inbound access from the ALB only",
    vpc_id=vpc.id,
    ingress=[
        aws.ec2.SecurityGroupIngressArgs(
            from_port=0,
            to_port=0,
            protocol="-1",
            security_groups=[lb_sg.id]
        ),
        aws.ec2.SecurityGroupIngressArgs(
            from_port=22,
            to_port=22,
            protocol="Tcp",
            cidr_blocks=["0.0.0.0/0"]
        )
    ],
    egress=[aws.ec2.SecurityGroupEgressArgs(
        from_port=0,
        to_port=0,
        protocol="-1",
        cidr_blocks=["0.0.0.0/0"]
    )]
)

# Key pair for EC2
rsa_key = tls.PrivateKey(
    resource_name="rsa-key",
    algorithm="RSA",
    rsa_bits=4096
)

keypair = aws.ec2.KeyPair(
    resource_name=f"{prefix}-KeyPair",
    key_name=f"{prefix}-EC2-KeyPair",
    public_key=rsa_key.public_key_openssh
)

# Launch configuration and EC2 instances
bastion = aws.ec2.Instance(
    resource_name=f"{prefix}-bastion-ec2",
    ami=ubuntu_ami,
    instance_type=aws.ec2.InstanceType.T3_MICRO,
    key_name=keypair.key_name,
    associate_public_ip_address=False,
    subnet_id=public_subnet_1.id,
    security_groups=[ec2_sg.id]
)

ec2_launch_config = aws.ec2.LaunchConfiguration(
    resource_name=f"{prefix}-instances-lc",
    image_id=ubuntu_ami,
    instance_type=aws.ec2.InstanceType.T3_MICRO,
    security_groups=[ec2_sg.id],
    key_name=keypair.key_name,
    associate_public_ip_address=False,
    user_data=init_script,
    opts=pulumi.ResourceOptions(depends_on=[ngw])
)

# Load balancer and target group
load_balancer = aws.lb.LoadBalancer(
    resource_name=f"{prefix}-alb",
    load_balancer_type="application",
    internal=False,
    security_groups=[lb_sg.id],
    subnets=[public_subnet_1.id, public_subnet_2.id]
)

default_target_group = aws.lb.TargetGroup(
    resource_name=f"{prefix}-tg",
    port=80,
    protocol="HTTP",
    vpc_id=vpc.id,
    health_check=aws.lb.TargetGroupHealthCheckArgs(
        path="/",
        port="traffic-port",
        healthy_threshold=5,
        unhealthy_threshold=2,
        timeout=2,
        interval=60,
        matcher="200"
    )
)

ec2_alb_http_listener = aws.lb.Listener(
    resource_name=f"{prefix}-alb-listener",
    load_balancer_arn=load_balancer.arn,
    port=80,
    protocol="HTTP",
    opts=pulumi.ResourceOptions(depends_on=[default_target_group]),
    default_actions=[aws.lb.ListenerDefaultActionArgs(
        type="forward",
        target_group_arn=default_target_group.arn
    )]
)

# Autoscaling
ec2_cluster = aws.autoscaling.Group(
    resource_name=f"{prefix}-autoscaling-group",
    min_size=autoscale_min,
    max_size=autoscale_max,
    desired_capacity=autoscale_desired,
    health_check_type="EC2",
    launch_configuration=ec2_launch_config.name,
    vpc_zone_identifiers=[private_subnet_1.id, private_subnet_2.id],
    target_group_arns=[default_target_group.arn]
)

autoscale_attachment = aws.autoscaling.Attachment(
    resource_name=f"{prefix}-asg-attachment",
    autoscaling_group_name=ec2_cluster.id,
    lb_target_group_arn=default_target_group.arn
)