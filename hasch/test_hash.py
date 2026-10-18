import os
import unittest
import hashlib
import tempfile
import time
from hash_checker import HashCalculator

class TestHashCalculator(unittest.TestCase):
    def setUp(self):
        # Création d'un fichier temporaire de test
        self.test_content = b"Bonjour, ceci est un test de verification de hash pour l'application Hash Guard !" * 10000  # Env. 800 Ko
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.write(self.test_content)
        self.temp_file.close()

    def tearDown(self):
        # Suppression du fichier temporaire
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)

    def test_hash_calculation_accuracy(self):
        # Calcul direct avec hashlib
        expected_md5 = hashlib.md5(self.test_content).hexdigest()
        expected_sha1 = hashlib.sha1(self.test_content).hexdigest()
        expected_sha256 = hashlib.sha256(self.test_content).hexdigest()

        results = {}
        error_msg = None
        completed = False

        def progress_cb(bytes_read, total_size):
            pass

        def success_cb(res):
            nonlocal results, completed
            results = res
            completed = True

        def error_cb(err):
            nonlocal error_msg, completed
            error_msg = err
            completed = True

        # Lancer le calculateur asynchrone
        calculator = HashCalculator(
            filepath=self.temp_file.name,
            progress_callback=progress_cb,
            success_callback=success_cb,
            error_callback=error_cb
        )
        calculator.start()

        # Attendre la fin du calcul
        timeout = 5.0
        start_time = time.time()
        while not completed and (time.time() - start_time) < timeout:
            time.sleep(0.1)

        # Vérifications
        self.assertTrue(completed, "Le calcul du hash a dépassé le délai imparti.")
        self.assertIsNone(error_msg, f"Une erreur est survenue lors du calcul : {error_msg}")
        self.assertEqual(results.get('md5'), expected_md5, "MD5 ne correspond pas !")
        self.assertEqual(results.get('sha1'), expected_sha1, "SHA-1 ne correspond pas !")
        self.assertEqual(results.get('sha256'), expected_sha256, "SHA-256 ne correspond pas !")
        print("\n[SUCCESS] Tous les tests de calcul de hash ont reussi avec succes !")

if __name__ == "__main__":
    unittest.main()
