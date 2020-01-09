/* audit-viewer-server

Copyright (C) 2008 Red Hat, Inc.  All rights reserved.
This copyrighted material is made available to anyone wishing to use, modify,
copy, or redistribute it subject to the terms and conditions of the GNU
General Public License v.2.  This program is distributed in the hope that it
will be useful, but WITHOUT ANY WARRANTY expressed or implied, including the
implied warranties of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU General Public License for more details.  You should have
received a copy of the GNU General Public License along with this program; if
not, write to the Free Software Foundation, Inc., 51 Franklin Street, Fifth
Floor, Boston, MA 02110-1301, USA.  Any Red Hat trademarks that are
incorporated in the source code or documentation are not subject to the GNU
General Public License and may only be used or replicated with the express
permission of Red Hat, Inc.

Red Hat Author: Miloslav Trmac <mitr@redhat.com> */
#include "config.h"

#include <assert.h>
#include <dirent.h>
#include <errno.h>
#include <error.h>
#include <fcntl.h>
#include <inttypes.h>
#include <libintl.h>
#include <locale.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#include "server.h"

#define _(X) gettext (X)

#define SOCKET_FILENO STDIN_FILENO

#define AUDIT_LOG_DIR LOCALSTATEDIR "/log/audit"

 /* Generic utilities */

#define STR__(X) #X
#define STR(X) STR__ (X)

/* Like read (), but avoid partial reads if possible. */
static ssize_t
full_read (int fd, void *buf, size_t size)
{
  ssize_t res, r;

  res = 0;
  while (size != 0 && (r = read (fd, buf, size)) != 0)
    {
      if (r < 0)
	return r;
      res += r;
      buf = (char *)buf + r;
      assert (size >= (size_t)r);
      size -= r;
    }
  return res;
}

/* Like write (), but handle partial writes. */
static ssize_t
full_write (int fd, const void *buf, size_t size)
{
  size_t left;

  left = size;
  while (left != 0)
    {
      ssize_t r;

      r = write (fd, buf, left);
      if (r < 0)
	return r;
      assert (r != 0);
      buf = (const char *)buf + r;
      assert (left >= (size_t)r);
      left -= r;
    }
  return size;
}

/* Like full_read (), but abort if the whole read could not be completed */
static void
read_or_fail (int fd, void *buf, size_t size)
{
  if ((size_t)full_read (fd, buf, size) != size)
    exit (EXIT_FAILURE);
}

/* Like full_write (), but abort if the whole write could not be completed */
static void
write_or_fail (int fd, const void *buf, size_t size)
{
  if ((size_t)full_write (fd, buf, size) != size)
    exit (EXIT_FAILURE);
}

/* Return a malloc ()ed concatenation of s1 and s2, or NULL */
static char *
concat (const char *s1, const char *s2)
{
  size_t len1, size2;
  char *res;

  len1 = strlen (s1);
  size2 = strlen (s2) + 1;
  res = malloc (len1 + size2);
  if (res != NULL)
    {
      memcpy (res, s1, len1);
      memcpy (res + len1, s2, size2);
    }
  return res;
}

 /* The server */

/* Print the usage message. */
static void
usage (void)
{
  puts (_("This program is only for use by audit-viewer and it should not be "
	  "run manually.\n"));
}

/* Handle command-line arguments. */
static void
handle_args (int argc, char *argv[])
{
  if (argc > 1)
    {
      if (strcmp (argv[1], "--help") == 0)
	{
	  usage ();
	  printf (_("\n"
		    "Report bugs to %s.\n"), PACKAGE_BUGREPORT);
	  exit (EXIT_SUCCESS);
	}
      if (strcmp (argv[1], "--version") == 0)
	{
	  puts (PACKAGE_NAME " " PACKAGE_VERSION);
	  puts (_("Copyright (C) 2008 Red Hat, Inc.  All rights reserved.\n"
		  "This software is distributed under the GPL v.2.\n"
		  "\n"
		  "This program is provided with NO WARRANTY, to the extent "
		  "permitted by law."));
	  exit (EXIT_SUCCESS);
	}
      usage ();
      exit (EXIT_FAILURE);
    }
}

/* Handle REQ_LIST_FILES */
static void
req_list_files (void)
{
  static const uint32_t end_marker; /* = 0; */

  DIR *dir;
  struct dirent *de;

  dir = opendir (AUDIT_LOG_DIR);
  if (dir == NULL)
    goto end;
  while ((de = readdir (dir)) != NULL)
    {
      uint32_t len_data;
      size_t len;

      if (strcmp (de->d_name, ".") == 0 || strcmp (de->d_name, "..") == 0)
	continue;
      len = strlen (de->d_name);
      len_data = len;
      if (len_data != len) /* If the assignment overflowed */
	continue;
      write_or_fail (SOCKET_FILENO, &len_data, sizeof (len_data));
      write_or_fail (SOCKET_FILENO, de->d_name, len);
    }
  closedir (dir);
 end:
  write_or_fail (SOCKET_FILENO, &end_marker, sizeof (end_marker));
}

/* Read a file specification from the client and return the relevant path.
   Abort if the specification.  The caller must free () the path. */
static char *
get_file_path (void)
{
  char buf[NAME_MAX + 1];
  uint32_t len;

  read_or_fail (SOCKET_FILENO, &len, sizeof (len));
  if (len > NAME_MAX)
    exit (EXIT_FAILURE);
  assert (len < sizeof (buf));
  read_or_fail (SOCKET_FILENO, buf, len);
  buf[len] = '\0';
  if (strchr (buf, '/') != NULL || strcmp (buf, ".") == 0
      || strcmp (buf, "..") == 0)
    exit (EXIT_FAILURE);
  return concat (AUDIT_LOG_DIR "/", buf);
}

/* Handle REQ_READ_FILE */
static void
req_read_file (void)
{
  char *path;
  int fd;
  uint32_t err;
  struct stat st;
  void *data;
  ssize_t res;
  uint64_t data_len;

  path = get_file_path ();
  fd = open (path, O_RDONLY);
  free (path);
  if (fd == -1)
    {
      err = errno;
      goto err;
    }
  if (fstat (fd, &st) != 0)
    {
      err = errno;
      goto err_fd;
    }
  /* Just to be sure, allow only regular files */
  if (!S_ISREG (st.st_mode))
    {
      err = EINVAL;
      goto err_fd;
    }
  /* If sizeof (off_t) <= sizeof (size_t), (size_t)st.st_size cannot overflow
     and (off_t)SIZE_MAX is negative. */
  if (sizeof (off_t) > sizeof (size_t) && st.st_size > (off_t)SIZE_MAX)
    {
      err = EFBIG;
      goto err_fd;
    }
  data = malloc (st.st_size);
  if (data == NULL)
    {
      err = errno;
      goto err_fd;
    }
  res = full_read (fd, data, st.st_size);
  if (res < 0)
    {
      err = errno;
      goto err_data;
    }
  data_len = res;
  close (fd);
  err = 0;
  write_or_fail (SOCKET_FILENO, &err, sizeof (err));
  write_or_fail (SOCKET_FILENO, &data_len, sizeof (data_len));
  write_or_fail (SOCKET_FILENO, data, data_len);
  free (data);
  return;

 err_data:
  free (data);
 err_fd:
  close (fd);
 err:
  write_or_fail (SOCKET_FILENO, &err, sizeof (err));
}

int
main (int argc, char *argv[])
{
  static const uint32_t server_hello = SERVER_HELLO;

  struct stat st;
  uint32_t req;
  ssize_t len;

  setlocale (LC_ALL, "");
  bindtextdomain (PACKAGE_NAME, LOCALEDIR);
  textdomain (PACKAGE_NAME);
  handle_args (argc, argv);
  if (fstat (SOCKET_FILENO, &st) != 0)
    error (EXIT_FAILURE, errno, "fstat (SOCKET_FILENO)");
  if (!S_ISSOCK (st.st_mode))
    error (EXIT_FAILURE, 0, _("The control file is not a socket"));
  write_or_fail (SOCKET_FILENO, &server_hello, sizeof (server_hello));
  while ((len = full_read (SOCKET_FILENO, &req, sizeof (req))) == sizeof (req))
    {
      switch (req)
	{
	case REQ_LIST_FILES:
	  req_list_files ();
	  break;

	case REQ_READ_FILE:
	  req_read_file ();
	  break;

	default:
	  error (EXIT_FAILURE, 0, _("Unknown server request %" PRIu32), req);
	}
    }
  if (len != 0)
    return EXIT_FAILURE;
  return EXIT_SUCCESS;
}
