/* audit-viewer-server protocol

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

#ifndef SERVER_H__
#define SERVER_H__

/* All transferred integers use the host byte order and bit representation. */

#define SERVER_HELLO 0x12345678

/* The server is started with an unix stream domain socket on STDIN_FILENO,
   sends 32-bit SERVER_HELLO, and waits for requests.  Each request starts with
   a 32-bit command: */
#define REQ_LIST_FILES 1 	/* Get a list of available audit log files */
#define REQ_READ_FILE 2		/* Read an audit log file */

/* REQ_LIST_FILES:
   The server sends a sequence of file name records.
   Each file name record consists of a 32-bit name length (not including the
   trailing NUL) followed by the file name (without a trailing NUL).
   The sequence is terminated by a name length equal to 0.
   (No errors are reported; on error, the sequence of file name records is
   quietly truncated.) */

/* REQ_READ_FILE:
   The client sends 32-bit file name length (not including the trailing NUL)
   followed by the file name (without a trailing NUL).  The file name length
   must be <= NAME_MAX.
   The server replies with a 32-bit errno value (0 for success).
   If errno is 0, the server sends a 64-bit file size, followed by file data.
   (This assumes no failures can occur after sending the errno value, so the
   server needs to read the file to memory.) */

#endif
