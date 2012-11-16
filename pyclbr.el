;;; pyclbr.el --- Python class/function browser

;; Copyright (C) 2012 Takafumi Arakaki

;; Author: Takafumi Arakaki <aka.tkf at gmail.com>

;; This file is NOT part of GNU Emacs.

;; pyclbr.el is free software: you can redistribute it and/or modify
;; it under the terms of the GNU General Public License as published by
;; the Free Software Foundation, either version 3 of the License, or
;; (at your option) any later version.

;; pyclbr.el is distributed in the hope that it will be useful,
;; but WITHOUT ANY WARRANTY; without even the implied warranty of
;; MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
;; GNU General Public License for more details.

;; You should have received a copy of the GNU General Public License
;; along with pyclbr.el.
;; If not, see <http://www.gnu.org/licenses/>.

;;; Commentary:

;;

;;; Code:

(eval-when-compile (require 'cl))
(require 'epc)


(defgroup pyclbr nil
  "Python class/function browser"
  :group 'python
  :prefix "pyclbr:")

(defvar pyclbr:source-dir (if load-file-name
                              (file-name-directory load-file-name)
                            default-directory))

(defvar pyclbr:epc nil)

(defvar pyclbr:server-script
  (expand-file-name "pyclbrepcserver.py" pyclbr:source-dir)
  "Full path to Jedi server script file ``pyclbrepcserver.py``.")


;;; Configuration

(defcustom pyclbr:server-command
  (list (let ((py (expand-file-name "env/bin/python" pyclbr:source-dir)))
          (if (file-exists-p py) py "python"))
        pyclbr:server-script)
  "Command used to run pyclbr server.

If you setup pyclbr requirements using ``make requirements`` command,
`pyclbr:server-command' should be automatically set to::

    '(\"PYCLBR:SOURCE-DIR/env/bin/python\"
      \"PYCLBR:SOURCE-DIR/pyclbrepcserver.py\")

Otherwise, it should be set to::

    '(\"python\" \"PYCLBR:SOURCE-DIR/pyclbrepcserver.py\")

If you want to use your favorite Python executable, set
`pyclbr:server-command' using::

    (setq pyclbr:server-command
          (list \"YOUR-FAVORITE-PYTHON\" pyclbr:server-script))

If you want to pass some arguments to the pyclbr server command,
use `pyclbr:server-command'."
  :group 'pyclbr)

(defcustom pyclbr:server-args nil
  "Command line arguments to be appended to `pyclbr:server-command'.

If you want to add some special `sys.path' when starting pyclbr
server, do something like this::

    (setq pyclbr:server-args
          '(\"--sys-path\" \"MY/SPECIAL/PATH\"
            \"--sys-path\" \"MY/OTHER/SPECIAL/PATH\"))

To see what other arguments pyclbr server can take, execute the
following command::

    python pyclbrepcserver.py --help"
  :group 'pyclbr)


;;; Server management

(defun pyclbr:start-server ()
  (if pyclbr:epc
      (message "pyclbr server is already started!")
    (let ((default-directory pyclbr:source-dir))
      (setq pyclbr:epc (epc:start-epc (car pyclbr:server-command)
                                      (append (cdr pyclbr:server-command)
                                              pyclbr:server-args))))
    (set-process-query-on-exit-flag
     (epc:connection-process (epc:manager-connection pyclbr:epc)) nil)
    (set-process-query-on-exit-flag
     (epc:manager-server-process pyclbr:epc) nil))
  pyclbr:epc)

(defun pyclbr:stop-server ()
  "Stop Pyclbr server.  Use this command when you want to restart
Pyclbr server (e.g., when you changed `pyclbr:server-command' or
`pyclbr:server-args').  Pyclbr srever will be restarted automatically
later when it is needed."
  (interactive)
  (if pyclbr:epc
      (epc:stop-epc pyclbr:epc)
    (message "Pyclbr server is already killed."))
  (setq pyclbr:epc nil))

(defun pyclbr:get-epc ()
  (or pyclbr:epc (pyclbr:start-server)))

(defun pyclbr:get-descriptions ()
  (epc:call-deferred (pyclbr:get-epc)
                     'get_descriptions
                     (list buffer-file-name)))

;;; Location

(defvar pyclbr:helm--candidates)

(defvar pyclbr:helm--source
  '((name . "Pyclbr")
    (candidates . pyclbr:helm--candidates)
    (recenter)
    (type . file-line)))

(defun pyclbr:helm-candidates ()
  (deferred:nextc (pyclbr:get-descriptions)
    (lambda (descriptions)
      (mapcar (lambda (x)
                (destructuring-bind (&key file lineno fullname
                                          &allow-other-keys)
                    x
                  (format "%s:%s: %s" file lineno fullname)))
              descriptions))))

(defun pyclbr:helm--deferred (helm)
  (lexical-let ((helm helm))
    (deferred:$
      (pyclbr:helm-candidates)
      (deferred:nextc it
        (lambda (pyclbr:helm--candidates)
          (funcall
           helm
           :sources (list pyclbr:helm--source)
           :buffer (format "*%s pyclbr*" helm)))))))

(defun helm-pyclbr ()
  (interactive)
  (pyclbr:helm--deferred 'helm))

(defun anything-pyclbr ()
  (interactive)
  (pyclbr:helm--deferred 'anything))


(provide 'pyclbr)

;;; pyclbr.el ends here
