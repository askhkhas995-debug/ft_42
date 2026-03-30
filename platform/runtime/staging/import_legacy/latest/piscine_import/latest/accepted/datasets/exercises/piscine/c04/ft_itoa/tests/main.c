#include <stdio.h>
#include <stdlib.h>

char	*ft_itoa(int nbr);

int main(int argc, char **argv)
{
	if (argc == 2)
	{
		char *res = ft_itoa(atoi(argv[1]));
		printf("%s\n", res);
		free(res);
	}
	return (0);
}
