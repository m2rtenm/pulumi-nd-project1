"""An Azure RM Python Pulumi program"""

import pulumi
from pulumi_azure_native import network
from pulumi_azure_native import resources
from pulumi_azure_native import compute
from pulumi import ResourceOptions
import base64

# Config and variables
config = pulumi.Config()

prefix = config.get("prefix")
location = config.get("location")
counter = config.get_int("counter")
username = config.get("username")
vm_size = config.get("vm_size")
disk_size = config.get_int("disk_size")
password = config.require("password")

# Resource group
resource_group = resources.ResourceGroup(
    resource_name=f"{prefix}-rg",
    location=location
)

# Virtual network
virtual_network = network.VirtualNetwork(
    resource_name=f"{prefix}-network",
    resource_group_name=resource_group.name,
    address_space=network.AddressSpaceArgs(
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
            source_address_prefix=subnet.address_prefixes[0],
            source_port_range="*",
            destination_address_prefix=subnet.address_prefixes[0],
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

# Public IP
public_ip = network.PublicIPAddress(
    resource_name=f"{prefix}-PublicIP",
    resource_group_name=resource_group.name,
    location=resource_group.location,
    public_ip_allocation_method=network.IpAllocationMethod.STATIC,
    sku=network.PublicIPAddressSkuArgs(name=network.PublicIPAddressSkuName.STANDARD)
)

# Load Balancer and its configuration
lb_frontend_ip = network.FrontendIPConfigurationArgs(
    name=f"{prefix}-LB-PublicIPAddress",
    public_ip_address=network.PublicIPAddressArgs(id=public_ip.id)
)

load_balancer = network.LoadBalancer(
    resource_name=f"{prefix}-lb",
    resource_group_name=resource_group.name,
    load_balancer_name="lb",
    location=resource_group.location,
    frontend_ip_configurations=[lb_frontend_ip],
    sku=network.LoadBalancerSkuArgs(name=network.LoadBalancerSkuName.STANDARD)
)

# Backend Address Pool for the Load Balancer
backend_pool = network.LoadBalancerBackendAddressPool(
    resource_name=f"{prefix}-BackendPool",
    resource_group_name=resource_group.name,
    load_balancer_name=load_balancer.name,

    opts=ResourceOptions(depends_on=[load_balancer])
)

# VM Availability Set
aset = compute.AvailabilitySet(
    resource_name=f"{prefix}-AvailabilitySet",
    resource_group_name=resource_group.name,
    location=resource_group.location,
    sku=compute.SkuArgs(name="Aligned"),
    platform_fault_domain_count=2
)

# Virtual Machines, Network Interfaces and Managed Disks
for i in range(counter):
    vm_name = f"{prefix}-vm-{i+1}"

    init_script = """#!/bin/bash
    echo "Hello, world!" > index.html
    nohup busybox httpd -f -p 80 &
    """

    disk = compute.Disk(
        resource_name=f"{prefix}-ManagedDisk-{i+1}",
        resource_group_name=resource_group.name,
        location=resource_group.location,
        disk_size_gb=disk_size,
        creation_data=compute.CreationDataArgs(create_option=compute.DiskCreateOptionTypes.EMPTY),
        sku=compute.DiskSkuArgs(name="Standard_LRS")
    )

    nic = network.NetworkInterface(
        resource_name=f"{prefix}-nic-{i+1}",
        resource_group_name=resource_group.name,
        location=resource_group.location,
        ip_configurations=[network.NetworkInterfaceIPConfigurationArgs(
            name="internal",
            subnet=network.SubnetArgs(id=subnet.id),
            private_ip_allocation_method=network.IpAllocationMethod.DYNAMIC,
            load_balancer_backend_address_pools=[network.BackendAddressPoolArgs(id=backend_pool.id)]
        )],
        network_security_group=network.NetworkSecurityGroupArgs(id=nsg.id)
    )

    vm = compute.VirtualMachine(
        resource_name=vm_name,
        resource_group_name=resource_group.name,
        location=resource_group.location,

        hardware_profile=compute.HardwareProfileArgs(vm_size=vm_size),

        network_profile=compute.NetworkProfileArgs(
            network_interfaces=[
                compute.NetworkInterfaceReferenceArgs(id=nic.id)
            ]
        ),

        os_profile=compute.OSProfileArgs(
            computer_name=vm_name,
            admin_username=username,
            admin_password=password,
            custom_data=base64.b64encode(init_script.encode("ascii")).decode("ascii"),
            linux_configuration=compute.LinuxConfigurationArgs(
                disable_password_authentication=False
            )
        ),

        availability_set=compute.SubResourceArgs(id=aset.id),

        storage_profile=compute.StorageProfileArgs(
            os_disk=compute.OSDiskArgs(
                caching=compute.CachingTypes.READ_WRITE,
                create_option=compute.DiskCreateOptionTypes.FROM_IMAGE,
                managed_disk=compute.ManagedDiskParametersArgs(storage_account_type="Standard_LRS")
            ),
            image_reference=compute.ImageReferenceArgs(
                publisher="canonical",
                offer="UbuntuServer",
                sku="18.04-LTS",
                version="latest"
            )
        )
    )