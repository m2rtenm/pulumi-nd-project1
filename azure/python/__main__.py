"""An Azure RM Python Pulumi program"""

import pulumi
from pulumi_azure_native import network
from pulumi_azure_native import resources
from pulumi_azure_native import compute

# Config and variables
config = pulumi.Config()

prefix = config.get("prefix")
location = config.get("location")
counter = config.get_int("counter")
username = config.get("username")
vm_size = config.get("vm_size")
disk_size = config.get_int("disk_size")

# Resource group
resource_group = resources.ResourceGroup(
    resource_name=f"{prefix}-rg",
    location=location
)

# Virtual network
virtual_network = network.VirtualNetwork(
    resource_name=f"{prefix}-network",
    address_spaces=network.AddressSpaceArgs(
        address_prefixes=["10.0.0.0/16"]
    )
)

# Subnet
subnet = network.Subnet(
    resource_name="internal",
    resource_group_name=resource_group.name,
    virtual_network_name=virtual_network.name,
    address_prefixes=["10.0.0.0/24"]
)

# Network Security Group
nsg = network.NetworkSecurityGroup(
    resource_name=f"{prefix}-nsg",
    resource_group_name=resource_group.name,
    security_rules=[
        network.SecurityRuleArgs(
            name="AllowInternalTraffic",
            priority=100,
            direction=network.SecurityRuleDirection.INBOUND,
            access=network.SecurityRuleAccess.ALLOW,
            protocol=network.SecurityRuleProtocol.TCP,
            source_address_prefix=[subnet.address_prefixes[0]],
            source_port_range="*",
            destination_address_prefix=[subnet.address_prefixes[0]],
            destination_port_range="*"
        ),
        network.SecurityRuleArgs(
            name="DenyInternetInbound",
            priority=200,
            direction=network.SecurityRuleDirection.INBOUND,
            access=network.SecurityRuleAccess.DENY,
            protocol=network.SecurityRuleProtocol.TCP,
            source_address_prefix="Internet",
            source_port_range="*",
            destination_address_prefix="*",
            destination_port_range="*"
        )
    ]
)

