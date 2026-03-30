#include <stdio.h>
#include <string.h>

char    *ft_strcpy(char *s1, char *s2);

int main(int argc, char **argv)
{
	char buf[4096];
	(void)argc;
	memset(buf, 0, sizeof(buf));
	ft_strcpy(buf, argv[1]);
	printf("%s\n", buf);
	return (0);
}
