#include <unistd.h>

void	ft_putchar(char c);

int	main(int argc, char **argv)
{
	char	value;

	value = 'a';
	if (argc > 1 && argv[1][0] != '\0')
		value = argv[1][0];
	ft_putchar(value);
	return (0);
}
