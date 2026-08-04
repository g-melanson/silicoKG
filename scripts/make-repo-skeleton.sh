ROOT="$PWD"
PIPELINE_STEPS=(1-ingestion 2-validation 3-transformation 4-integration 5-publish)
STEP_FILES=(__init__.py __main__.py cli.py context.py engine.py README.md runner.py errors.py)
SOURCES=(ncbi gene-ontology reactome cell-map)
# dirs
mkdir -p "$ROOT/pipeline"/{1-ingestion,2-validation,3-transformation,4-integration,5-publish}
mkdir -p "$ROOT/pipeline"/{1-ingestion,2-validation,3-transformation,4-integration,5-publish}/tests
mkdir -p "$ROOT/sources"
mkdir -p "$ROOT/schemas/domain"
# root + shared files
for f in README.md; do [[ -e "$ROOT/$f" ]] || touch "$ROOT/$f"; done
for f in base.py register.py; do [[ -e "$ROOT/sources/$f" ]] || touch "$ROOT/sources/$f"; done
for f in imports.yaml slots.yaml classes.yaml; do [[ -e "$ROOT/schemas/$f" ]] || touch "$ROOT/schemas/$f"; done
[[ -e "$ROOT/schemas/domain/gene-or-gene-product.yaml" ]] || touch "$ROOT/schemas/domain/gene-or-gene-product.yaml"
# per pipeline step
for step in "${PIPELINE_STEPS[@]}"; do
  dir="$ROOT/pipeline/$step"
  for f in "${STEP_FILES[@]}"; do [[ -e "$dir/$f" ]] || touch "$dir/$f"; done
done
# per source
for src in "${SOURCES[@]}"; do
  dir="$ROOT/sources/$src"
  mkdir -p "$dir"
  [[ -e "$dir/adapter.py" ]] || touch "$dir/adapter.py"
  [[ -e "$dir/${src}.schema.yaml" ]] || touch "$dir/${src}.schema.yaml"
  [[ -e "$dir/${src}.transform.yaml" ]] || touch "$dir/${src}.transform.yaml"
done
