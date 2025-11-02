class IPv4CIDRSolver:

    def __init__(
        self,
        host: str,
        desired: int,
        bits: int,
    ):
        self.host = host
        self.subnets_desired = desired
        self.subnet_bits = bits

        host_ip, mask = self.host.split('/', maxsplit=1)

        self.host_ip = host_ip
        self._host_mask_string = f'/{mask}'
        self.host_mask = int(mask)

        self.subnet_mask = 32 - bits

        self._host_octets = [
            int(octet) for octet in self.host.strip(self._host_mask_string).split('.')
        ]
    
    def provision_subnets(self):
        subnet_requested_ips = 2**self.subnet_bits
        host_available_ips = 2**(32 - self.host_mask)

        total_ips_requested = subnet_requested_ips * self.subnets_desired
        if host_available_ips < total_ips_requested:
            return []

        return [
            self._provision_subnet(
                subnet_requested_ips,
                idx
            ) for idx in range(self.subnets_desired)
        ]

    
    def _provision_subnet(
        self,
        requested_ips: int,
        idx: int,
    ):
        increment = requested_ips
        octet_idx = -1
        if requested_ips > 255:
            increment /= 256
            octet_idx -= 1

        increment *= idx

        subnet = list(self._host_octets)

        subnet[octet_idx] += increment

        subnet_base_ip = '.'.join([
            str(octet) for octet in subnet
        ])

        return f'{subnet_base_ip}/{self.subnet_mask}'



    
