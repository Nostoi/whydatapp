.PHONY: css css-watch
css:
	npx tailwindcss -i src/why/web/static/css/tailwind.src.css -o src/why/web/static/css/tailwind.css --minify

css-watch:
	npx tailwindcss -i src/why/web/static/css/tailwind.src.css -o src/why/web/static/css/tailwind.css --watch
