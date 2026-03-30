#include <stdio.h>
#include <stdlib.h>

unsigned int	lcm(unsigned int a, unsigned int b);

int main(int argc, char **argv)
{
	if (argc == 3)
		printf("%u\n", lcm(atoi(argv[1]), atoi(argv[2])));
	return (0);
}
