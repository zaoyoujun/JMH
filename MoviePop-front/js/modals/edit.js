function openEditModal(movie) {
  state.editMovie = movie;
  const form = document.getElementById("editForm");
  form.elements.title.value = movie.title || "";
  form.elements.name.value = movie.name || "";
  form.elements.type.value = movie.type || "电影";
  form.elements.year.value = movie.year || 2024;
  form.elements.intro.value = movie.intro || "";
  openModal("editModal");
}

