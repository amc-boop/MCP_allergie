# Règles du serveur MCP Open Food Facts

Toutes les règles de décision sont dans `regles.py`. Ce fichier ne fait aucun appel réseau : il décide uniquement quoi répondre à partir des données d'Open Food Facts.

**Principe général :** on ne répond jamais « sans risque ». Si une donnée manque ou est incertaine, la réponse est « inconnu » ou « non renseigné », jamais une valeur inventée.

## Les 21 règles

### Contrôles sur les entrées

1. Un code-barres doit contenir 8 à 13 chiffres ; sinon, erreur sans appel à l'API.
2. Le texte saisi est mis en minuscules, sans accents (« Œufs » devient « oeufs »).
3. Un allergène, régime ou label inconnu donne une erreur avec la liste des choix possibles.

### Allergènes (`verifier_allergene`)

4. Si l'allergène figure dans la liste des allergènes du produit, la réponse est « contient ».
5. S'il figure dans la liste des traces, la réponse est « traces possibles ».
6. S'il n'apparaît nulle part, ou si le produit est introuvable, la réponse est « inconnu » (jamais « sans risque »).

### Régimes (`verifier_regime`) : vegan, végétarien, sans huile de palme

7. Si l'analyse des ingrédients dit oui, la réponse est « oui (estimé) ».
8. Si l'analyse dit non, la réponse est « non ».
9. Si l'analyse dit « peut-être », ne sait pas, ou si le produit est introuvable, la réponse est « inconnu ».

### Labels (`verifier_label`) : bio, commerce équitable, sans gluten, Label Rouge

10. Si le label est déclaré sur le produit, la réponse est « présent ».
11. S'il n'est pas déclaré, la réponse est « non signalé » (jamais « absent » ni « faux »).
12. Si le produit est introuvable, la réponse est « inconnu ».

### Fiche produit (`fiche_produit`)

13. Un champ absent, vide ou marqué « unknown » est affiché « non renseigné ».

### Nutrition (`infos_nutrition`)

14. Le Nutri-Score et le score environnemental sont donnés en lettre majuscule, sinon « non renseigné ».
15. Le groupe NOVA et les valeurs pour 100 g sont donnés en nombre, sinon « non renseigné ».
16. Un zéro est une vraie valeur : 0 g de sucre reste 0.
17. Une liste d'additifs vide veut dire « aucun additif enregistré » ; un champ absent donne « non renseigné ».

### Avertissements

18. Les réponses sur les allergènes rappellent que les données peuvent être incomplètes et qu'« inconnu » ne veut pas dire « sans risque ».
19. Les réponses sur les régimes rappellent que c'est une estimation, pas une certification.
20. Les réponses sur les labels rappellent qu'ils sont déclarés par des contributeurs et qu'il faut vérifier l'emballage.
21. Pour le label « sans gluten », un rappel précise que ce n'est pas une garantie médicale et qu'il faut aussi utiliser `verifier_allergene`.

---

## Annexe : valeurs acceptées et étiquettes Open Food Facts

### 14 allergènes

| Allergène | Étiquette Open Food Facts |
|---|---|
| gluten | `en:gluten` |
| crustaces | `en:crustaceans` |
| oeufs | `en:eggs` |
| poisson | `en:fish` |
| arachides | `en:peanuts` |
| soja | `en:soybeans` |
| lait | `en:milk` |
| fruits a coque | `en:nuts` |
| celeri | `en:celery` |
| moutarde | `en:mustard` |
| sesame | `en:sesame-seeds` |
| sulfites | `en:sulphur-dioxide-and-sulphites` |
| lupin | `en:lupin` |
| mollusques | `en:molluscs` |

Synonymes acceptés : oeuf, arachide, crustace, mollusque, sulfite.

### 3 régimes

| Régime | Étiquette « oui » | Étiquette « non » |
|---|---|---|
| vegan | `en:vegan` | `en:non-vegan` |
| vegetarien | `en:vegetarian` | `en:non-vegetarian` |
| sans huile de palme | `en:palm-oil-free` | `en:palm-oil` |

Synonymes acceptés : vegetarian, vegane, sans palme.

### 4 labels

| Label | Étiquettes reconnues |
|---|---|
| bio | `en:organic`, `fr:ab-agriculture-biologique`, `en:eu-organic` |
| commerce equitable | `en:fair-trade`, `en:fairtrade-international`, `en:max-havelaar`, `en:max-havelaar-france`, `en:fair-for-life` |
| sans gluten | `en:no-gluten` |
| label rouge | `fr:label-rouge` |

Synonymes acceptés : biologique, ab, bio europeen → bio ; equitable, fair trade, fairtrade → commerce equitable.
