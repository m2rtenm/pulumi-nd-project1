# Azure Infrastructure Operations Project: Deploying a scalable IaaS web server in Azure
This project was written both in Python and YAML using Pulumi.

## Architecture

The final solution of this project consists of following parts:

* Resource group to host all resources
* Virtual network and a subnet on that virtual network
* Network security group which ensures that explicitly allows access to other VMs on the subnet and deny direct access from the internet
* Network interfaces for VMs
* Public IP
* Load balancer which needs a backend address pool and address pool association for the network interface and the load balancer
* Virtual machine availability set
* Virtual machines
* Managed disks for the virtual machines